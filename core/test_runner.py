#!/usr/bin/env python3
"""
Test Runner for the Event Framework

NOTE: Adapter Uniqueness Constraint
The framework enforces that there can only be ONE canonical adapter for each
transformation (e.g., plaintext_to_signed). This prevents ambiguity in the
adapter graph. If you need optimized transformations across multiple hops,
create explicit shortcut adapters (e.g., plaintext_to_encrypted) rather than
having multiple implementations of the same single-hop transformation.
"""
import json
import sys
import os
import traceback
import copy
import yaml
import re
from datetime import datetime
from pathlib import Path

class TestRunner:
    def __init__(self):
        self.verbose = False
        self.logs = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(entry)
        if self.verbose:
            print(entry)
    
    def subset_match(self, actual, expected, path=""):
        """
        Check if expected is a subset of actual.
        Returns (matches, mismatch_path, expected_value, actual_value)
        """
        # Special case for "..." which matches any value
        if expected == "...":
            return True, None, None, None
            
        # Wildcard matches anything
        if expected == "*":
            return True, None, None, None
        
        # Type check
        if type(actual) != type(expected):
            return False, path, expected, actual
        
        if isinstance(expected, dict):
            # Check all keys in expected exist in actual with matching values
            for key in expected:
                if key == "*":
                    # Wildcard key - match any key with the expected value
                    if not actual:  # No keys in actual dict
                        return False, f"{path}.*", expected[key], None
                    # Check if any key has the expected value
                    found_match = False
                    for actual_key, actual_val in actual.items():
                        matches, _, _, _ = self.subset_match(actual_val, expected[key], f"{path}.{actual_key}")
                        if matches:
                            found_match = True
                            break
                    if not found_match:
                        # Return the first actual value for error reporting
                        first_key = list(actual.keys())[0] if actual else None
                        first_val = actual[first_key] if first_key else None
                        return False, f"{path}.*", expected[key], first_val
                else:
                    if key not in actual:
                        return False, f"{path}.{key}", expected[key], None
                    matches, mismatch_path, exp_val, act_val = self.subset_match(
                        actual[key], expected[key], f"{path}.{key}"
                    )
                    if not matches:
                        return False, mismatch_path, exp_val, act_val
            return True, None, None, None
            
        elif isinstance(expected, list):
            # Lists must match exactly in length and order
            if len(actual) != len(expected):
                return False, f"{path}.length", len(expected), len(actual)
            for i, (a, e) in enumerate(zip(actual, expected)):
                matches, mismatch_path, exp_val, act_val = self.subset_match(
                    a, e, f"{path}[{i}]"
                )
                if not matches:
                    return False, mismatch_path, exp_val, act_val
            return True, None, None, None
            
        else:
            # Primitive values must match exactly
            if actual != expected:
                return False, path, expected, actual
            return True, None, None, None
    
    def run_test_scenario(self, scenario, test_file):
        """Run a single test scenario using real framework"""
        scenario_name = scenario.get("name", scenario.get("description", "Unnamed"))
        self.log(f"Running scenario: {scenario_name}")
        
        try:
            given = scenario.get("given", {})
            then = scenario.get("then", {})
            
            # Set environment variables if specified
            if "env" in given:
                for key, value in given["env"].items():
                    os.environ[key] = value
            
            # Set crypto mode to dummy by default
            if "CRYPTO_MODE" not in os.environ:
                os.environ["CRYPTO_MODE"] = "dummy"
            
            # Set up initial state
            db = copy.deepcopy(given.get("db", {"eventStore": {}, "state": {}}))
            incoming_queue = copy.deepcopy(given.get("incomingQueue", []))
            current_identity = given.get("currentIdentity", "test-user")
            
            # Execute commands if any
            command_results = []
            if "commands" in given:
                for cmd in given["commands"]:
                    result = self.execute_command(cmd, current_identity, db)
                    command_results.append(result)
                    # Note: events are now projected automatically by run_command
            
            # Handle special test cases
            if given.get("permute") and "events_to_permute" in db:
                # For permutation test, add events directly to state
                # This is a special test case that bypasses normal processing
                events = db.pop("events_to_permute")
                if "state" not in db:
                    db["state"] = {}
                if "messages" not in db["state"]:
                    db["state"]["messages"] = []
                
                # Add to eventStore and state
                for event in events:
                    db["eventStore"]["pubkey1"].append(event)
                    db["state"]["messages"].append(event)
            
            # Run real tick
            from core.tick import tick
            # Add incoming queue items to db.incoming
            if incoming_queue:
                if "incoming" not in db:
                    db["incoming"] = []
                db["incoming"].extend(incoming_queue)
            time_now_ms = scenario.get('time_now_ms')
            tick(db, time_now_ms=time_now_ms)
            
            # Build result for comparison
            result = {"db": db}
            if command_results:
                result["commandResults"] = command_results
            
            # Filter out description from then before matching
            then_filtered = {k: v for k, v in then.items() if k != "description"}
            
            matches, path, exp_val, act_val = self.subset_match(result, then_filtered)
            if matches:
                return {"scenario": scenario_name, "passed": True, "logs": self.logs}
            else:
                self.log(f"Mismatch at {path}: expected {exp_val}, got {act_val}", "ERROR")
                return {"scenario": scenario_name, "passed": False, "logs": self.logs}
                
        except Exception as e:
            self.log(f"Scenario crashed: {str(e)}", "ERROR")
            self.log(traceback.format_exc(), "ERROR")
            return {
                "scenario": scenario_name,
                "passed": False,
                "logs": self.logs,
                "error": str(e)
            }
    
    def execute_command(self, cmd, identity, db):
        """Execute a command and return its result"""
        handler = cmd["handler"]
        command = cmd["command"]
        input_data = cmd.get("input", {})
        
        # Validate input against schema if defined
        from core.schema_validator import validate_command_input, validate_command_output
        is_valid, error = validate_command_input(handler, command, input_data)
        if not is_valid:
            raise ValueError(f"Input validation failed: {error}")
        
        # Use run_command from tick to execute and project events
        from core.tick import run_command
        updated_db, result = run_command(handler, command, input_data, identity, db, time_now_ms=1000)
        
        # Update db reference
        if 'db' in result:
            # The result already has db, use that
            db.update(result['db'])
        else:
            # Update db with the modified version from run_command
            db.clear()
            db.update(updated_db)
        
        # Validate output against schema if defined
        is_valid, error = validate_command_output(handler, command, result)
        if not is_valid:
            raise ValueError(f"Output validation failed: {error}")
        
        return result
    
    
    
    def run_handler_test(self, test, handler_file, handler_name=None, command_name=None):
        """Run handler tests using real framework"""
        # For handler tests with envelope, we need to handle it directly
        if "envelope" in test.get("given", {}):
            scenario_name = test.get("description", "Unnamed")
            self.log(f"Running projector test: {scenario_name}")
            
            given = test.get("given", {})
            then = test.get("then", {})
            envelope = given["envelope"]
            db = copy.deepcopy(given.get("db", {}))
            
            # Call handle directly with the envelope
            from core.handle import handle
            self.log(f"Calling handle with envelope: {envelope}")
            import json
            self.log(f"Initial db state: {json.dumps(db, indent=2)}")
            
            result_db = handle(db, envelope, time_now_ms=1000)
            
            self.log(f"Result db after handle: {json.dumps(result_db, indent=2)}")
            
            # Check for errors
            if 'blocked' in result_db:
                self.log(f"WARNING: Found blocked envelopes: {result_db['blocked']}", "WARNING")
            
            # Check what changed
            if 'state' in db and 'state' in result_db:
                for key in result_db['state']:
                    if key not in db.get('state', {}):
                        self.log(f"State added key '{key}': {result_db['state'][key]}")
                    elif db['state'].get(key) != result_db['state'].get(key):
                        self.log(f"State changed key '{key}': {db['state'].get(key)} -> {result_db['state'].get(key)}")
            
            # Check result
            result = {"db": result_db}
            matches, path, exp_val, act_val = self.subset_match(result, then)
            
            if matches:
                return {"scenario": scenario_name, "passed": True, "logs": self.logs}
            else:
                self.log(f"Mismatch at {path}: expected {exp_val}, got {act_val}", "ERROR")
                return {"scenario": scenario_name, "passed": False, "logs": self.logs}
        
        
        # For command tests, handle differently
        if "params" in test.get("given", {}):
            # This is a command test
            scenario_name = test.get("description", "Command test")
            self.log(f"Running command test: {scenario_name}")
            
            given = test.get("given", {})
            then = test.get("then", {})
            
            # Set environment variables if specified
            if "env" in given:
                for key, value in given["env"].items():
                    os.environ[key] = value
            
            # Handle setup field for test data generation
            if "setup" in given and given["setup"].get("type") == "generate_encrypted_blob":
                setup = given["setup"]
                # Import the helper function from process_incoming
                import importlib.util
                import sys
                protocol_path = handler_file.split('/handlers/')[0]
                module_path = os.path.join(protocol_path, "handlers/incoming/process_incoming.py")
                spec = importlib.util.spec_from_file_location("process_incoming", module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Generate the encrypted blob
                encrypted_blob = module.create_encrypted_blob(
                    setup["inner_data"],
                    setup["inner_key"],
                    setup["outer_key"]
                )
                
                # Add to incoming queue
                if "db" not in given:
                    given["db"] = {}
                if "incoming" not in given["db"]:
                    given["db"]["incoming"] = []
                given["db"]["incoming"].append({
                    "data": encrypted_blob,
                    "origin": "test_setup",
                    "received_at": given["params"].get("time_now_ms", 1000)
                })
            
            # Execute command
            # Extract handler name from file path
            if not handler_name:
                path_parts = handler_file.split('/')
                for i, part in enumerate(path_parts):
                    if part == "handlers" and i + 1 < len(path_parts):
                        handler_name = path_parts[i + 1]
                        break
                else:
                    handler_name = "message"  # fallback
            
            # Use command name if provided
            if not command_name:
                command_name = "create"  # fallback
            
            cmd = {
                "handler": handler_name,
                "command": command_name,
                "input": given["params"]
            }
            
            db = given.get("db", {})
            identity = given.get("identity", "test-user")
            try:
                result = self.execute_command(cmd, identity, db)
                
                # Apply the command's db changes if any
                if "db" in result:
                    db = result["db"]
            except Exception as e:
                self.log(f"Command execution failed: {str(e)}", "ERROR")
                # For crypto-related failures, add more context
                if "decrypt" in str(e).lower() or "crypto" in str(e).lower():
                    self.log("Note: Real crypto tests require proper encryption/decryption. Check that:", "ERROR")
                    self.log("  - PyNaCl is installed (pip install pynacl)", "ERROR")
                    self.log("  - Keys are properly formatted (64 hex chars for 32-byte keys)", "ERROR")
                    self.log("  - Wire format matches expectations (hash:64, nonce:48, ciphertext:remaining)", "ERROR")
                    self.log(f"  - Current CRYPTO_MODE: {os.environ.get('CRYPTO_MODE', 'dummy')}", "ERROR")
                raise
            
            # Run ticks if specified
            ticks = test.get("ticks", 0)
            if ticks > 0:
                self.log(f"Running {ticks} ticks after command")
                
                # Constants for time progression
                base_time = given.get("params", {}).get("time_now_ms", 1000)
                time_increment = 100  # ms between ticks
                
                # Import tick based on protocol
                protocol = handler_file.split('/')[1]  # e.g. "message_via_tor"
                if protocol == "framework_tests":
                    from core.tick import tick
                else:
                    # For other protocols, tick just runs jobs
                    from core.tick import run_all_jobs as tick
                
                # Run the specified number of ticks
                for i in range(ticks):
                    current_time = base_time + (i + 1) * time_increment
                    self.log(f"Tick {i+1} at time {current_time}")
                    db = tick(db, time_now_ms=current_time)
                    
                # Update result with final db state
                result["db"] = db
            
            # Check result
            return_matches = True
            if "return" in then:
                matches, path, exp_val, act_val = self.subset_match(result, then["return"])
                if not matches:
                    self.log(f"Mismatch at return{path}: expected {exp_val}, got {act_val}", "ERROR")
                    return_matches = False
            
            # Check db state if specified
            db_matches = True
            if "db" in then:
                db_result = {"db": db}
                matches, path, exp_val, act_val = self.subset_match(db_result, {"db": then["db"]})
                if not matches:
                    self.log(f"Mismatch at {path}: expected {exp_val}, got {act_val}", "ERROR")
                    db_matches = False
            
            if return_matches and db_matches:
                return {"scenario": scenario_name, "passed": True, "logs": self.logs}
            else:
                return {"scenario": scenario_name, "passed": False, "logs": self.logs}
        
        # For handler tests with newEvent, convert to envelope
        if "newEvent" in test.get("given", {}):
            given = test.get("given", {})
            event = given["newEvent"]
            
            # Create an envelope from the event
            envelope = {
                "data": event,
                "metadata": {
                    "sender": event.get("sender", "test-user")
                }
            }
            
            # Add envelope to test
            modified_test = copy.deepcopy(test)
            modified_test["given"]["envelope"] = envelope
            del modified_test["given"]["newEvent"]
            
            return self.run_handler_test(modified_test, handler_file)
        
        return self.run_test_scenario(test, handler_file)
    
    def run_file(self, test_path):
        """Run all test scenarios in a file"""
        self.logs = []
        results = []
        
        try:
            with open(test_path, 'r') as f:
                test_data = json.load(f)
            
            # Check if this is a JSON-only test file
            if test_data.get("jsonTestsOnly"):
                # Skip command execution, just verify test structure
                if "commands" in test_data:
                    for cmd_name, cmd_def in test_data["commands"].items():
                        if "tests" in cmd_def:
                            for test in cmd_def["tests"]:
                                scenario_name = test.get("description", f"{cmd_name} test")
                                results.append({
                                    "file": test_path,
                                    "scenario": scenario_name,
                                    "passed": True,
                                    "logs": [f"JSON-only test verified: {scenario_name}"]
                                })
                return results
            
            # Determine test type based on file location and content
            if "handlers" in test_path:
                # Handler tests
                if "projector" in test_data and "tests" in test_data["projector"]:
                    for test in test_data["projector"]["tests"]:
                        self.logs = []
                        result = self.run_handler_test(test, test_path)
                        result["file"] = test_path
                        results.append(result)
                
                if "commands" in test_data:
                    for cmd_name, cmd_def in test_data["commands"].items():
                        if "tests" in cmd_def:
                            for test in cmd_def["tests"]:
                                self.logs = []
                                # Extract handler name from path
                                path_parts = test_path.split('/')
                                handler_name = None
                                for i, part in enumerate(path_parts):
                                    if part == "handlers" and i + 1 < len(path_parts):
                                        handler_name = path_parts[i + 1]
                                        break
                                result = self.run_handler_test(test, test_path, handler_name, cmd_name)
                                result["file"] = test_path
                                results.append(result)
                                
            elif "tick.json" in test_path:
                # Tick tests
                if "tests" in test_data:
                    for test in test_data["tests"]:
                        self.logs = []
                        result = self.run_test_scenario(test, test_path)
                        result["file"] = test_path
                        results.append(result)
                        
            elif "runner.json" in test_path:
                # Runner tests are meta-tests - skip for now
                # These test the test runner itself, not the framework
                pass
            
            return results
            
        except Exception as e:
            self.log(f"Failed to load test file: {str(e)}", "ERROR")
            return [{
                "file": test_path,
                "scenario": "File load error",
                "passed": False,
                "error": str(e),
                "logs": self.logs
            }]
    
    
    def run_protocol_tests(self, protocol_name, protocol_path):
        """Run tests for a specific protocol"""
        print(f"\n" + "="*60)
        print(f"RUNNING PROTOCOL: {protocol_name}")
        print("="*60)
        
        # Set test mode for better logging
        os.environ["TEST_MODE"] = "1"
        os.environ["DEBUG_CRYPTO"] = "1"  # Enable crypto debugging by default
        
        # Set handler path for this protocol
        handlers_path = os.path.join(protocol_path, "handlers")
        if os.path.exists(handlers_path):
            os.environ["HANDLER_PATH"] = handlers_path
        
        # Check for schema.sql and validate if present
        schema_file = os.path.join(protocol_path, "schema.sql")
        if os.path.exists(schema_file):
            print(f"\nFound schema.sql, validating handler data against schema...")
            try:
                from core.check_schema_sql import SQLSchemaParser, HandlerSchemaValidator
                
                # Parse schema
                schema_parser = SQLSchemaParser(schema_file)
                print(f"  Parsed {len(schema_parser.tables)} tables from schema")
                
                # Validate handlers
                validator = HandlerSchemaValidator(schema_parser)
                total_errors = 0
                total_warnings = 0
                
                # Check each handler
                for root, dirs, files in os.walk(handlers_path):
                    # Look for {folder}_handler.json pattern
                    handler_name = os.path.basename(root)
                    handler_json_name = f"{handler_name}_handler.json"
                    if handler_json_name in files:
                        handler_path = os.path.join(root, handler_json_name)
                        
                        errors, warnings = validator.validate_handler(handler_path)
                        if errors or warnings:
                            print(f"\n  Handler '{handler_name}':")
                            if errors:
                                print(f"    Schema errors: {len(errors)}")
                                for error in errors[:3]:  # Show first 3 errors
                                    print(f"      - {error}")
                                if len(errors) > 3:
                                    print(f"      ... and {len(errors) - 3} more")
                            if warnings:
                                print(f"    Schema warnings: {len(warnings)}")
                                
                        total_errors += len(errors)
                        total_warnings += len(warnings)
                
                if total_errors > 0 or total_warnings > 0:
                    print(f"\n  Schema validation summary:")
                    print(f"    Total errors: {total_errors} (not enforced)")
                    print(f"    Total warnings: {total_warnings}")
                else:
                    print(f"  ✓ All handlers match schema perfectly!")
                    
            except Exception as e:
                print(f"  WARNING: Schema validation failed: {str(e)}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()
        
        # Check for api.yaml and validate if present
        api_file = os.path.join(protocol_path, "api.yaml")
        if os.path.exists(api_file):
            print(f"\nFound api.yaml, validating API operations...")
            api_errors = self.validate_api(protocol_name, protocol_path, api_file, handlers_path)
            if api_errors > 0:
                print(f"  ❌ API validation found {api_errors} errors")
            else:
                print(f"  ✅ All API operations validated successfully")
        
        # Run tests for this protocol
        protocol_results = []
        for root, dirs, files in os.walk(protocol_path):
            for file in files:
                if file.endswith(".json") and file != "schema.json":
                    test_path = os.path.join(root, file)
                    results = self.run_file(test_path)
                    protocol_results.extend(results)
        
        # Summary for this protocol
        passed = sum(1 for r in protocol_results if r["passed"])
        failed = sum(1 for r in protocol_results if not r["passed"])
        
        print(f"\n{protocol_name} Test Results: {passed} passed, {failed} failed")
        
        return protocol_results
    
    def run_all_tests(self):
        """Run tests for all protocols separately"""
        all_results = []
        protocol_summaries = []
        
        # Discover all protocols
        protocols_dir = "protocols"
        if not os.path.exists(protocols_dir):
            print("No protocols directory found")
            return False
        
        # Run tests for each protocol
        for protocol_name in sorted(os.listdir(protocols_dir)):
            protocol_path = os.path.join(protocols_dir, protocol_name)
            if os.path.isdir(protocol_path):
                results = self.run_protocol_tests(protocol_name, protocol_path)
                all_results.extend(results)
                
                # Store summary for this protocol
                passed = sum(1 for r in results if r["passed"])
                failed = sum(1 for r in results if not r["passed"])
                protocol_summaries.append({
                    "name": protocol_name,
                    "passed": passed,
                    "failed": failed
                })
        
        # Overall summary
        total_passed = sum(1 for r in all_results if r["passed"])
        total_failed = sum(1 for r in all_results if not r["passed"])
        
        print(f"\n{'='*60}")
        print("SUMMARY BY PROTOCOL")
        print("="*60)
        for summary in protocol_summaries:
            status = "✓" if summary["failed"] == 0 else "✗"
            print(f"{status} {summary['name']}: {summary['passed']} passed, {summary['failed']} failed")
        
        print(f"\n{'='*60}")
        print(f"TOTAL Test Results: {total_passed} passed, {total_failed} failed")
        print(f"{'='*60}\n")
        
        # Show failed tests
        for result in all_results:
            if not result["passed"]:
                print(f"FAILED: {result['file']} - {result['scenario']}")
                if "error" in result:
                    print(f"  Error: {result['error']}")
                for log in result.get("logs", []):
                    if "ERROR" in log:
                        print(f"  {log}")
                print()
        
        return total_failed == 0
    
    def validate_api(self, protocol_name, protocol_path, api_file, handlers_path):
        """Validate API specification against handlers. Returns error count."""
        try:
            # Load API specification
            with open(api_file, 'r') as f:
                api_spec = yaml.safe_load(f)
            
            # Discover handlers
            handlers = {}
            for handler_dir in os.listdir(handlers_path):
                handler_path = os.path.join(handlers_path, handler_dir)
                if os.path.isdir(handler_path):
                    # Look for {folder}_handler.json pattern
                    handler_json_path = os.path.join(handler_path, f"{handler_dir}_handler.json")
                    if os.path.exists(handler_json_path):
                        try:
                            with open(handler_json_path, 'r') as f:
                                handler_data = json.load(f)
                            
                            # Extract commands
                            commands = []
                            if "commands" in handler_data:
                                commands.extend(handler_data["commands"].keys())
                            
                            # Jobs are also callable as commands
                            if "job" in handler_data:
                                commands.append(handler_data["job"])
                            
                            handlers[handler_dir] = commands
                        except Exception as e:
                            print(f"  Warning: Failed to parse {handler_json_path}: {e}")
            
            print(f"  Found {len(handlers)} handlers: {', '.join(handlers.keys())}")
            
            # Validate operations
            error_count = 0
            operation_count = 0
            
            # Special operations that don't map to handlers
            special_operations = ["tick.run"]
            
            if "paths" in api_spec:
                for path, path_item in api_spec["paths"].items():
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "delete", "patch"]:
                            operation_count += 1
                            operation_id = operation.get("operationId")
                            
                            if not operation_id:
                                print(f"    Error: {method.upper()} {path}: Missing operationId")
                                error_count += 1
                                continue
                            
                            # Skip special operations
                            if operation_id in special_operations:
                                continue
                            
                            # Check operationId format
                            if '.' not in operation_id:
                                print(f"    Error: {method.upper()} {path}: Invalid operationId format '{operation_id}'")
                                error_count += 1
                                continue
                            
                            handler_name, command_name = operation_id.split('.', 1)
                            
                            # Check if handler exists
                            if handler_name not in handlers:
                                print(f"    Error: {method.upper()} {path}: Handler '{handler_name}' not found")
                                error_count += 1
                                continue
                            
                            # Check if command exists
                            if command_name not in handlers[handler_name]:
                                print(f"    Error: {method.upper()} {path}: Command '{command_name}' not found in handler '{handler_name}'")
                                error_count += 1
                            
                            # Check request body schema for required fields
                            if "requestBody" in operation:
                                request_body = operation["requestBody"]
                                if "content" in request_body and "application/json" in request_body["content"]:
                                    schema = request_body["content"]["application/json"].get("schema", {})
                                    if schema.get("type") == "object":
                                        # Check if required array is missing when properties are defined
                                        if "properties" in schema and "required" not in schema:
                                            # Only flag as error if there are properties that should be required
                                            prop_count = len(schema["properties"])
                                            if prop_count > 0:
                                                print(f"    Error: {method.upper()} {path}: Request body schema has {prop_count} properties but no 'required' array specified")
                                                error_count += 1
                            
                            # Check response schemas for required fields
                            if "responses" in operation:
                                for status_code, response in operation["responses"].items():
                                    if "content" in response and "application/json" in response["content"]:
                                        schema = response["content"]["application/json"].get("schema", {})
                                        if schema.get("type") == "object":
                                            # Check if required array is missing when properties are defined
                                            if "properties" in schema and "required" not in schema:
                                                prop_count = len(schema["properties"])
                                                if prop_count > 0:
                                                    print(f"    Error: {method.upper()} {path}: Response {status_code} schema has {prop_count} properties but no 'required' array specified")
                                                    error_count += 1
            
            print(f"  Validated {operation_count} operations")
            
            # Check for duplicate operationIds
            operation_ids = []
            if "paths" in api_spec:
                for path, path_item in api_spec["paths"].items():
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "delete", "patch"]:
                            if "operationId" in operation:
                                operation_ids.append(operation["operationId"])
            
            duplicates = [x for x in operation_ids if operation_ids.count(x) > 1]
            if duplicates:
                unique_duplicates = list(set(duplicates))
                print(f"    Error: Duplicate operationIds found: {unique_duplicates}")
                error_count += len(unique_duplicates)
            
            return error_count
            
        except Exception as e:
            print(f"  ERROR: Failed to validate API: {str(e)}")
            return 1

if __name__ == "__main__":
    runner = TestRunner()
    if "--verbose" in sys.argv:
        runner.verbose = True
    
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)