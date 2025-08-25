"""
Core command execution module.
Handles running commands and projecting their events.
"""
import importlib.util
import os
from core.handler_discovery import get_handler_path
from core.handle import handle


def run_command(handler_name, command_name, input_data, db=None, time_now_ms=None):
    """
    Execute a command and project any returned events.
    Returns the modified db and command result.
    
    This is a first-class operation used by:
    - API endpoints to execute user commands
    - Tick to run periodic jobs
    - Tests to execute test scenarios
    """
    # Get handler base path
    handler_base = os.environ.get("HANDLER_PATH", "handlers")
    
    # Get command module path
    module_path = get_handler_path(handler_name, command_name, handler_base)
    if not module_path:
        raise ValueError(f"Command not found: {handler_name}/{command_name}")
    
    # Load and execute command
    spec = importlib.util.spec_from_file_location(command_name, module_path)
    command_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(command_module)
    
    # Execute command
    try:
        result = command_module.execute(input_data, db)
    except Exception as e:
        # Add context to the error
        import traceback
        error_msg = f"Error in {handler_name}.{command_name}: {str(e)}"
        if os.environ.get("TEST_MODE"):
            print(f"[command] {error_msg}")
            print(f"[command] Traceback: {traceback.format_exc()}")
        raise Exception(error_msg) from e
    
    # If command returned db modifications, apply them
    if isinstance(result, dict) and 'db' in result:
        # Update the existing db instead of replacing it
        for key, value in result['db'].items():
            db[key] = value
    
    # Project any new events returned by the command
    if isinstance(result, dict) and 'newEvents' in result:
        for event in result['newEvents']:
            # Create envelope for the event
            envelope = {
                'data': event,
                'metadata': {
                    'selfGenerated': True
                }
            }
            # Project the event using handle
            db = handle(db, envelope, time_now_ms)
    
    return db, result