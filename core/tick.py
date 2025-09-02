"""
Tick processing.

Purposefully minimal: discover handlers with jobs and run them in order.
Jobs run independently; failures are logged but do not stop the tick.
"""
import os
import logging
from core.command import run_command
from core.handle import handle_batch

logger = logging.getLogger(__name__)


def tick(db, time_now_ms=None):
    """Run all configured jobs once and return the updated `db`."""
    return run_all_jobs(db, time_now_ms)


# run_command has been moved to core.command module


def run_all_jobs(db, time_now_ms):
    """Discover and execute each handler's job command if declared."""
    from core.handler_discovery import discover_handlers, load_handler_config

    handler_base = os.environ.get("HANDLER_PATH", "handlers")
    handler_names = discover_handlers(handler_base)

    for handler_name in handler_names:
        config = load_handler_config(handler_name, handler_base)
        job_command = (config or {}).get('job')
        if not job_command:
            continue

        if job_command not in (config.get('commands') or {}):
            continue

        try:
            input_data = {"time_now_ms": time_now_ms}
            if os.environ.get("TEST_MODE"):
                print(f"[tick] Running job {handler_name}.{job_command}")
            db, _ = run_command(handler_name, job_command, input_data, db, time_now_ms)
        except Exception as e:
            logger.error(f"Job {handler_name}.{job_command} failed: {e}")
            continue

        # next handler

    return db
