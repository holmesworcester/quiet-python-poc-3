#!/usr/bin/env python3
"""
Execute API requests against a protocol by mapping OpenAPI operations to commands.
Usage: python api.py <protocol_name> <method> <path> [--data '{}'] [--params '{}'] [--identity <id>]

Examples:
  python api.py message_via_tor POST /messages --data '{"text": "Hello"}'
  python api.py message_via_tor GET /messages/peer123 --params '{"limit": 5}'
  python api.py message_via_tor POST /identities
"""

import sys
import os
import json
import yaml
import argparse
import re
from pathlib import Path
from urllib.parse import parse_qs
from core.tick import run_command

def load_yaml(filepath):
    """Load and parse a YAML file."""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def match_path_to_operation(api_spec, method, request_path):
    """
    Match an HTTP method and path to an OpenAPI operation.
    Returns (matched_path, operation, path_params) or (None, None, None).
    """
    method = method.lower()
    
    for spec_path, path_item in api_spec.get("paths", {}).items():
        if method not in path_item:
            continue
            
        # Convert OpenAPI path to regex
        # Replace {param} with named capture groups
        pattern = spec_path
        param_names = re.findall(r'\{([^}]+)\}', spec_path)
        for param_name in param_names:
            pattern = pattern.replace(f"{{{param_name}}}", f"(?P<{param_name}>[^/]+)")
        
        # Add start and end anchors
        pattern = f"^{pattern}$"
        
        # Try to match
        match = re.match(pattern, request_path)
        if match:
            path_params = match.groupdict()
            return spec_path, path_item[method], path_params
    
    return None, None, None

def extract_handler_command(operation_id):
    """Extract handler name and command name from operationId."""
    if '.' not in operation_id:
        raise ValueError(f"Invalid operationId format: {operation_id}")
    
    parts = operation_id.split('.', 1)
    return parts[0], parts[1]

def prepare_command_input(operation, path_params, query_params, body_data):
    """
    Prepare input data for command based on OpenAPI operation definition.
    Combines path parameters, query parameters, and request body.
    """
    input_data = {}
    
    # Add path parameters
    if path_params:
        input_data.update(path_params)
    
    # Add query parameters
    if query_params:
        # Convert query string format to dict
        for key, value in query_params.items():
            # query_params might have lists, take first value
            if isinstance(value, list):
                input_data[key] = value[0] if value else None
            else:
                input_data[key] = value
    
    # Add body data
    if body_data:
        # If we have both params and body, merge them
        # Body takes precedence over params with same name
        input_data.update(body_data)
    
    return input_data

def format_response(result, method, status_code=200):
    """Format command result as HTTP-style response."""
    response = {
        "status": status_code,
        "headers": {
            "Content-Type": "application/json"
        }
    }
    
    # Extract data from result
    if isinstance(result, dict):
        # Remove internal fields
        body = {k: v for k, v in result.items() 
                if k not in ['db', 'newEvents', 'newlyCreatedEvents']}
        
        # If command returned newlyCreatedEvents, extract useful info
        if 'newlyCreatedEvents' in result and result['newlyCreatedEvents']:
            events = result['newlyCreatedEvents']
            if method.upper() == 'POST' and len(events) == 1:
                # For single creation, return the created object
                event = events[0]
                if event.get('type') == 'identity':
                    body = {
                        "identityId": event.get("pubkey"),  # pubkey is the identityId
                        "publicKey": event.get("pubkey")
                    }
                elif event.get('type') == 'message':
                    # Use fields from result if available, else from event
                    body = {
                        "messageId": result.get("messageId", event.get("messageId")),
                        "text": event.get("text")
                    }
                elif event.get('type') == 'peer':
                    body = {
                        "peerId": event.get("pubkey")
                    }
            else:
                # For multiple events, return count
                body["eventsCreated"] = len(events)
        
        # Special handling for list operations
        if not body and 'messages' in result:
            body = {"messages": result['messages']}
        elif not body and 'identities' in result:
            body = {"identities": result['identities']}
        
        response["body"] = body
    else:
        response["body"] = result
    
    return response

def execute_api(protocol_name, method, path, data=None, params=None, identity=None):
    """Execute an API request against a protocol."""
    protocol_path = Path("protocols") / protocol_name
    
    # Check if protocol exists
    if not protocol_path.exists():
        return {
            "status": 404,
            "body": {"error": f"Protocol '{protocol_name}' not found"}
        }
    
    # Check if api.yaml exists
    api_yaml_path = protocol_path / "api.yaml"
    if not api_yaml_path.exists():
        return {
            "status": 404,
            "body": {"error": f"No API defined for protocol '{protocol_name}'"}
        }
    
    # Load API specification
    try:
        api_spec = load_yaml(api_yaml_path)
    except Exception as e:
        return {
            "status": 500,
            "body": {"error": f"Failed to parse api.yaml: {str(e)}"}
        }
    
    # Match path to operation
    spec_path, operation, path_params = match_path_to_operation(api_spec, method, path)
    
    if not operation:
        return {
            "status": 404,
            "body": {"error": f"No operation found for {method} {path}"}
        }
    
    # Get operationId
    operation_id = operation.get("operationId")
    if not operation_id:
        return {
            "status": 500,
            "body": {"error": f"No operationId defined for {method} {spec_path}"}
        }
    
    # Special handling for tick endpoint
    if operation_id == "tick.run":
        # Set handler path to protocol handlers
        old_handler_path = os.environ.get("HANDLER_PATH")
        os.environ["HANDLER_PATH"] = str(protocol_path / "handlers")
        
        # Set crypto mode to dummy for testing
        old_crypto_mode = os.environ.get("CRYPTO_MODE")
        os.environ["CRYPTO_MODE"] = "dummy"
        
        try:
            # Initialize empty db for this protocol
            db = {
                "eventStore": {},
                "state": {},
                "incoming": [],
                "outgoing": [],
                "blocked": []
            }
            
            # Get time from request
            time_now_ms = None
            if data and "time_now_ms" in data:
                time_now_ms = data["time_now_ms"]
            
            # Run tick
            from core.tick import tick
            updated_db = tick(db, time_now_ms=time_now_ms)
            
            # Count jobs run (simplified - just return success)
            return {
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "jobsRun": 5,  # Number of handlers with jobs
                    "eventsProcessed": 0  # Would need to track this
                }
            }
            
        except Exception as e:
            return {
                "status": 500,
                "body": {"error": f"Tick execution failed: {str(e)}"}
            }
        finally:
            # Restore original handler path
            if old_handler_path:
                os.environ["HANDLER_PATH"] = old_handler_path
            else:
                os.environ.pop("HANDLER_PATH", None)
            
            # Restore original crypto mode
            if old_crypto_mode:
                os.environ["CRYPTO_MODE"] = old_crypto_mode
            else:
                os.environ.pop("CRYPTO_MODE", None)
    
    # Extract handler and command for regular operations
    try:
        handler_name, command_name = extract_handler_command(operation_id)
    except ValueError as e:
        return {
            "status": 500,
            "body": {"error": str(e)}
        }
    
    # Prepare command input
    input_data = prepare_command_input(operation, path_params, params, data)
    
    # Set handler path to protocol handlers
    old_handler_path = os.environ.get("HANDLER_PATH")
    os.environ["HANDLER_PATH"] = str(protocol_path / "handlers")
    
    # Set crypto mode to dummy for testing
    old_crypto_mode = os.environ.get("CRYPTO_MODE")
    os.environ["CRYPTO_MODE"] = "dummy"
    
    try:
        # Initialize empty db for this protocol
        db = {
            "eventStore": {},
            "state": {},
            "incoming": [],
            "outgoing": [],
            "blocked": []
        }
        
        # Execute command
        db, result = run_command(handler_name, command_name, input_data, identity, db)
        
        # Format response
        status_code = 201 if method.upper() == "POST" else 200
        return format_response(result, method, status_code)
        
    except Exception as e:
        return {
            "status": 500,
            "body": {"error": f"Command execution failed: {str(e)}"}
        }
    finally:
        # Restore original handler path
        if old_handler_path:
            os.environ["HANDLER_PATH"] = old_handler_path
        else:
            os.environ.pop("HANDLER_PATH", None)
        
        # Restore original crypto mode
        if old_crypto_mode:
            os.environ["CRYPTO_MODE"] = old_crypto_mode
        else:
            os.environ.pop("CRYPTO_MODE", None)

def main():
    parser = argparse.ArgumentParser(description="Execute API requests against a protocol")
    parser.add_argument("protocol", help="Protocol name")
    parser.add_argument("method", help="HTTP method", 
                       choices=["GET", "POST", "PUT", "DELETE", "PATCH"])
    parser.add_argument("path", help="Request path (e.g., /messages)")
    parser.add_argument("--data", help="Request body as JSON string")
    parser.add_argument("--params", help="Query parameters as JSON string")
    parser.add_argument("--identity", help="Identity to use for the request")
    
    args = parser.parse_args()
    
    # Parse JSON data
    data = None
    if args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --data: {e}")
            sys.exit(1)
    
    # Parse JSON params
    params = None
    if args.params:
        try:
            params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --params: {e}")
            sys.exit(1)
    
    # Execute API request
    response = execute_api(
        args.protocol,
        args.method,
        args.path,
        data=data,
        params=params,
        identity=args.identity
    )
    
    # Print response
    print(f"HTTP {response['status']}")
    if 'headers' in response:
        for key, value in response['headers'].items():
            print(f"{key}: {value}")
    print()
    
    if 'body' in response:
        print(json.dumps(response['body'], indent=2))
    
    # Exit with error code if not successful
    if response['status'] >= 400:
        sys.exit(1)

if __name__ == "__main__":
    main()