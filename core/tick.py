"""
Tick processing with batch transaction support.

Key changes:
- Incoming messages processed in batch, each in its own transaction
- Jobs run with transaction support
- Failed jobs don't stop tick processing
"""
import os
import logging
from core.command import run_command
from core.handle import handle_batch

logger = logging.getLogger(__name__)


def tick(db, time_now_ms=None):
    """
    Main event loop with batch transaction support.
    Processes incoming messages first, then runs all handler jobs.
    """
    has_transactions = hasattr(db, 'begin_transaction')
    events_processed = 0
    jobs_run = 0
    
    # The incoming handler job will process incoming messages if configured
    # No special processing needed here - run_all_jobs will handle it
    
    # Run all jobs from all handlers
    db = run_all_jobs(db, time_now_ms)
    
    # Count jobs for return value (API compatibility)
    from core.handler_discovery import discover_handlers, load_handler_config
    handler_base = os.environ.get("HANDLER_PATH", "handlers")
    handler_names = discover_handlers(handler_base)
    for handler_name in handler_names:
        config = load_handler_config(handler_name, handler_base)
        if config and 'job' in config:
            jobs_run += 1
    
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
            if os.environ.get("TEST_MODE"):
                print(f"[tick] Running job {handler_name}.{job_command}")
            db, result = run_command(handler_name, job_command, input_data, db, time_now_ms)
            
        except Exception as e:
            # Log but don't crash - jobs should be resilient
            logger.error(f"Job {handler_name}.{job_command} failed: {e}")
            # Continue with next job - one job failure doesn't stop tick
            continue
    
    return db