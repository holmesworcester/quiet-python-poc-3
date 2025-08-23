import importlib.util
import os
from core.handler_discovery import get_handler_path
from core.handle import handle


def tick(db, time_now_ms=None, current_identity=None):
    """
    Main event loop - runs all handler jobs.
    The incoming handler job now handles message decryption and routing.
    """
    # Run all jobs from all handlers (including the incoming handler)
    db = run_all_jobs(db, time_now_ms)
    
    return db


def run_command(handler_name, command_name, input_data, identity, db, time_now_ms=None):
    """
    Execute a command and project any returned events.
    Returns the modified db and command result.
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
    result = command_module.execute(input_data, identity, db)
    
    # If command returned db modifications, apply them
    if isinstance(result, dict) and 'db' in result:
        db = result['db']
    
    # Project any new events returned by the command
    if isinstance(result, dict) and 'newEvents' in result:
        for event in result['newEvents']:
            # Create envelope for the event
            envelope = {
                'data': event,
                'metadata': {
                    'selfGenerated': True,
                    'sender': identity
                }
            }
            # Project the event
            db = handle(db, envelope, time_now_ms, identity)
    
    return db, result


def run_all_jobs(db, time_now_ms):
    """
    Discover and run all jobs from all handlers.
    Jobs are commands specified in handler.json with a "job" field.
    Jobs run without a specific identity context.
    """
    import os
    from core.handler_discovery import discover_handlers, load_handler_config
    
    # Get handler base path
    handler_base = os.environ.get("HANDLER_PATH", "handlers")
    
    # Discover all handlers
    handler_names = discover_handlers(handler_base)
    
    # Run each handler's job if it exists
    for handler_name in handler_names:
        # Load handler config to check for job
        config = load_handler_config(handler_name, handler_base)
        if not config or 'job' not in config:
            continue
            
        job_command = config['job']
        
        # Check if this command exists in the handler's commands
        if 'commands' not in config or job_command not in config['commands']:
            continue
            
        try:
            # Execute the job command using run_command
            # Jobs run without identity context
            input_data = {"time_now_ms": time_now_ms}
            db, result = run_command(handler_name, job_command, input_data, None, db, time_now_ms)
            
        except Exception as e:
            # Log but don't crash - jobs should be resilient
            print(f"Error running job {job_command} for {handler_name}: {e}")
            continue
    
    return db