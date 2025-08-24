#!/usr/bin/env python3
"""
Validates that a protocol's API specification correctly maps to existing handlers and commands.
Usage: python check_api.py <protocol_name>
"""

import sys
import os
import json
import yaml
from pathlib import Path
import re

def load_yaml(filepath):
    """Load and parse a YAML file."""
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def load_json(filepath):
    """Load and parse a JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def get_protocol_handlers(protocol_path):
    """Discover all handlers and their commands in a protocol."""
    handlers = {}
    handlers_dir = protocol_path / "handlers"
    
    if not handlers_dir.exists():
        return handlers
    
    for handler_dir in handlers_dir.iterdir():
        if handler_dir.is_dir():
            handler_json_path = handler_dir / "handler.json"
            if handler_json_path.exists():
                try:
                    handler_data = load_json(handler_json_path)
                    handler_name = handler_dir.name
                    
                    # Extract commands
                    commands = []
                    if "commands" in handler_data:
                        commands.extend(handler_data["commands"].keys())
                    
                    # Jobs are also callable as commands
                    if "job" in handler_data:
                        commands.append(handler_data["job"])
                    
                    handlers[handler_name] = {
                        "commands": commands,
                        "data": handler_data
                    }
                except Exception as e:
                    print(f"Warning: Failed to parse {handler_json_path}: {e}")
    
    return handlers

def extract_path_parameters(path):
    """Extract parameter names from an OpenAPI path."""
    return re.findall(r'\{([^}]+)\}', path)

def validate_operation(operation_id, method, path, operation, handlers):
    """Validate a single API operation."""
    errors = []
    warnings = []
    
    # Special cases that don't map to handlers
    special_operations = ["tick.run"]
    if operation_id in special_operations:
        return errors, warnings  # No validation needed for special operations
    
    # Check operationId format
    if '.' not in operation_id:
        errors.append(f"Invalid operationId format '{operation_id}' - expected 'handler.command'")
        return errors, warnings
    
    handler_name, command_name = operation_id.split('.', 1)
    
    # Check if handler exists
    if handler_name not in handlers:
        errors.append(f"Handler '{handler_name}' not found for operationId '{operation_id}'")
        return errors, warnings
    
    # Check if command exists
    if command_name not in handlers[handler_name]["commands"]:
        errors.append(f"Command '{command_name}' not found in handler '{handler_name}'")
    
    # Check path parameters
    path_params = extract_path_parameters(path)
    if path_params:
        # Check if parameters are defined in the operation
        if "parameters" not in operation:
            errors.append(f"Path '{path}' has parameters {path_params} but no parameters defined")
        else:
            defined_params = {p["name"] for p in operation["parameters"] if p.get("in") == "path"}
            missing_params = set(path_params) - defined_params
            if missing_params:
                errors.append(f"Path parameters {missing_params} not defined in operation")
    
    # Check for common patterns
    if method.upper() == "GET" and "create" in command_name:
        warnings.append(f"GET {path} maps to '{command_name}' - consider using POST for creation")
    
    if method.upper() == "POST" and ("list" in command_name or "get" in command_name):
        warnings.append(f"POST {path} maps to '{command_name}' - consider using GET for queries")
    
    return errors, warnings

def check_api(protocol_name):
    """Check API specification for a protocol."""
    protocol_path = Path("protocols") / protocol_name
    
    # Check if protocol exists
    if not protocol_path.exists():
        print(f"Error: Protocol '{protocol_name}' not found")
        return False
    
    # Check if api.yaml exists
    api_yaml_path = protocol_path / "api.yaml"
    if not api_yaml_path.exists():
        print(f"No api.yaml found for protocol '{protocol_name}'")
        return True  # Not an error, protocol may not have an API
    
    print(f"Checking API for protocol: {protocol_name}")
    print(f"API spec: {api_yaml_path}")
    
    # Load API specification
    try:
        api_spec = load_yaml(api_yaml_path)
    except Exception as e:
        print(f"Error: Failed to parse api.yaml: {e}")
        return False
    
    # Load handlers
    handlers = get_protocol_handlers(protocol_path)
    print(f"Found {len(handlers)} handlers: {', '.join(handlers.keys())}")
    
    # Validate OpenAPI structure
    if "openapi" not in api_spec:
        print("Error: Missing 'openapi' field in api.yaml")
        return False
    
    if "paths" not in api_spec:
        print("Error: Missing 'paths' field in api.yaml")
        return False
    
    # Check all operations
    all_errors = []
    all_warnings = []
    operation_count = 0
    
    for path, path_item in api_spec["paths"].items():
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                operation_count += 1
                operation_id = operation.get("operationId")
                
                if not operation_id:
                    all_errors.append(f"{method.upper()} {path}: Missing operationId")
                    continue
                
                errors, warnings = validate_operation(
                    operation_id, method, path, operation, handlers
                )
                
                if errors:
                    for error in errors:
                        all_errors.append(f"{method.upper()} {path}: {error}")
                
                if warnings:
                    for warning in warnings:
                        all_warnings.append(f"{method.upper()} {path}: {warning}")
    
    # Report results
    print(f"\nValidated {operation_count} operations")
    
    if all_errors:
        print(f"\n❌ Found {len(all_errors)} errors:")
        for error in all_errors:
            print(f"  - {error}")
    else:
        print("\n✅ All operationIds map to valid handlers and commands")
    
    if all_warnings:
        print(f"\n⚠️  Found {len(all_warnings)} warnings:")
        for warning in all_warnings:
            print(f"  - {warning}")
    
    # Additional checks
    print("\nAdditional checks:")
    
    # Check for duplicate operationIds
    operation_ids = []
    for path, path_item in api_spec["paths"].items():
        for method, operation in path_item.items():
            if method in ["get", "post", "put", "delete", "patch"]:
                if "operationId" in operation:
                    operation_ids.append(operation["operationId"])
    
    duplicates = [x for x in operation_ids if operation_ids.count(x) > 1]
    if duplicates:
        print(f"  - ❌ Duplicate operationIds found: {set(duplicates)}")
    else:
        print(f"  - ✅ No duplicate operationIds")
    
    # Check for unused handlers
    used_handlers = set()
    for op_id in operation_ids:
        if '.' in op_id:
            used_handlers.add(op_id.split('.')[0])
    
    unused_handlers = set(handlers.keys()) - used_handlers
    if unused_handlers:
        print(f"  - ℹ️  Handlers not exposed via API: {', '.join(unused_handlers)}")
    
    return len(all_errors) == 0

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_api.py <protocol_name>")
        sys.exit(1)
    
    protocol_name = sys.argv[1]
    success = check_api(protocol_name)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()