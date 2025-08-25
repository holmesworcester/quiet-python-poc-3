import os
from core.command import run_command


def tick(db, time_now_ms=None):
    """
    Main event loop - runs all handler jobs.
    The incoming handler job now handles message decryption and routing.
    """
    # Run all jobs from all handlers (including the incoming handler)
    db = run_all_jobs(db, time_now_ms)
    
    return db


# run_command has been moved to core.command module


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
            input_data = {"time_now_ms": time_now_ms}
            db, result = run_command(handler_name, job_command, input_data, db, time_now_ms)
            
        except Exception as e:
            # Log but don't crash - jobs should be resilient
            print(f"Error running job {job_command} for {handler_name}: {e}")
            continue
    
    return db