"""
Command execution and event projection.

Executes a handler command, applies any direct infrastructure updates, and
projects returned events through the framework. If the database supports
transactions, the entire operation is atomic.
"""
import importlib.util
import os
import logging
import time
import uuid
from core.handler_discovery import get_handler_path
from core.handle import handle

# Set up logging
logger = logging.getLogger(__name__)

def is_infrastructure_update(key, value, db):
    """Return True if a direct update targets infrastructure state only."""
    # Direct infrastructure keys are always allowed
    if key in ['incoming', 'eventStore']:
        return True
    
    # Only allow 'state.outgoing' within the 'state' container
    if key == 'state' and isinstance(value, dict):
        current_state = db.get('state', {})
        for state_key, state_value in value.items():
            if state_key == 'outgoing':
                continue
            if state_key in current_state and current_state[state_key] != state_value:
                return False
        return True
    
    return False


def run_command(handler_name, command_name, input_data, db=None, time_now_ms=None):
    """
    Execute a command and project any returned events.
    Returns the modified db and command result.
    
    This is a first-class operation used by:
    - API endpoints to execute user commands
    - Tick to run periodic jobs
    - Tests to execute test scenarios
    """
    # If db supports retry, use it
    if hasattr(db, 'with_retry'):
        return db.with_retry(lambda: _run_command_with_tx(
            handler_name, command_name, input_data, db, time_now_ms
        ))
    else:
        return _run_command_with_tx(handler_name, command_name, input_data, db, time_now_ms)


def _run_command_with_tx(handler_name, command_name, input_data, db, time_now_ms):
    """Internal function that runs command with transaction"""
    handler_base = os.environ.get("HANDLER_PATH", "handlers")
    
    module_path = get_handler_path(handler_name, command_name, handler_base)
    if not module_path:
        raise ValueError(f"Command not found: {handler_name}/{command_name}")
    
    # Load command module
    spec = importlib.util.spec_from_file_location(command_name, module_path)
    command_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(command_module)
    
    # Allow commands to manage their own transactions when needed
    manage_tx = bool(getattr(command_module, 'MANAGE_TRANSACTIONS', False))
    has_transactions = hasattr(db, 'begin_transaction')
    if has_transactions and not manage_tx:
        db.begin_transaction()
    
    try:
        # Execute command
        try:
            result = command_module.execute(input_data, db)
        except Exception as e:
            import traceback
            error_msg = f"Error in {handler_name}.{command_name}: {str(e)}"
            if os.environ.get("TEST_MODE"):
                print(f"[command] {error_msg}")
                print(f"[command] Traceback: {traceback.format_exc()}")
            raise Exception(error_msg) from e
        
        # Apply safe direct updates (only when framework manages the transaction)
        if not manage_tx and isinstance(result, dict) and 'db' in result:
            for key, value in result['db'].items():
                # Prevent domain state changes outside events
                if has_transactions and not is_infrastructure_update(key, value, db):
                    raise ValueError(
                        f"Command '{command_name}' attempted to modify domain state '{key}'. "
                        f"Domain state must be modified through events."
                    )
                db[key] = value
        
        # Project any new events/envelopes returned by the command
        if not manage_tx and isinstance(result, dict) and ('newEnvelopes' in result or 'newEvents' in result):
            items = result.get('newEnvelopes') or result.get('newEvents') or []
            for item in items:
                # Accept either full envelopes ({data, metadata}) or raw event dicts
                if isinstance(item, dict) and 'data' in item:
                    envelope = item  # assume already-formed envelope
                else:
                    envelope = {'data': item, 'metadata': {}}
                # Project within the same transaction when supported
                db = handle(db, envelope, time_now_ms, auto_transaction=False)
        
        # Commit when successful
        if has_transactions and not manage_tx:
            db.commit()
            
    except Exception as e:
        if has_transactions and not manage_tx:
            db.rollback()
        raise
    
    return db, result
