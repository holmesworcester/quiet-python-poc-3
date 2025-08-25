"""
Core command execution module.
Handles running commands and projecting their events.

Key changes:
- Commands wrapped in transactions for atomicity
- Infrastructure state validation
- newEvents processed within same transaction
"""
import importlib.util
import os
import time
import logging
from core.handler_discovery import get_handler_path
from core.handle import handle

# Set up logging
logger = logging.getLogger(__name__)

# Infrastructure paths that commands can modify directly
INFRASTRUCTURE_PATHS = ['state.outgoing', 'incoming', 'eventStore']


def is_infrastructure_update(key, value, db):
    """Validate if an update is to infrastructure state"""
    # Direct infrastructure paths
    if key in ['incoming', 'eventStore']:
        return True
    
    # Check state updates
    if key == 'state' and isinstance(value, dict):
        # Only allow updates to infrastructure within state
        current_state = db.get('state', {})
        for state_key, state_value in value.items():
            if state_key == 'outgoing':
                continue  # Infrastructure
            elif state_key in current_state:
                # Check if trying to modify domain state
                if current_state[state_key] != state_value:
                    return False  # Domain state modification attempted
        return True
    
    # All other paths are domain state
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
    
    # Check if db supports transactions
    has_transactions = hasattr(db, 'begin_transaction')
    
    # Start transaction if supported
    if has_transactions:
        db.begin_transaction()
    
    try:
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
        
        # Validate and apply direct updates
        if isinstance(result, dict) and 'db' in result:
            for key, value in result['db'].items():
                # For compatibility, skip validation if db is plain dict
                if has_transactions and not is_infrastructure_update(key, value, db):
                    raise ValueError(
                        f"Command '{command_name}' attempted to modify domain state '{key}'. "
                        f"Domain state must be modified through events."
                    )
                db[key] = value
        
        # Project any new events returned by the command
        if isinstance(result, dict) and 'newEvents' in result:
            for event in result['newEvents']:
                # Generate a unique event ID
                import uuid
                event_id = str(uuid.uuid4())
                
                # Create envelope for the event
                metadata = {
                    'selfGenerated': True,
                    'eventId': event_id,
                    'timestamp': time_now_ms or int(time.time() * 1000)
                }
                
                # If event has received_by, move it to metadata
                if 'received_by' in event:
                    metadata['received_by'] = event['received_by']
                    # Remove from event data to avoid duplication
                    event_copy = event.copy()
                    del event_copy['received_by']
                else:
                    event_copy = event

                # For self-generated events that include a pubkey but no received_by,
                # set received_by to the event pubkey. This ensures identity and peer
                # creation events are recorded as belonging to the created identity
                # in the eventStore (otherwise UI shows Received by: N/A).
                if metadata.get('selfGenerated') and 'received_by' not in metadata:
                    possible_pubkey = None
                    try:
                        possible_pubkey = event_copy.get('pubkey')
                    except Exception:
                        possible_pubkey = None
                    if possible_pubkey:
                        metadata['received_by'] = possible_pubkey
                
                envelope = {
                    'data': event_copy,
                    'metadata': metadata
                }
                # Project the event using handle (auto_transaction=False since we're in a transaction)
                db = handle(db, envelope, time_now_ms, auto_transaction=False)
        
        # Commit transaction if supported
        if has_transactions:
            db.commit()
            
    except Exception as e:
        # Rollback on any error
        if has_transactions:
            db.rollback()
        raise
    
    return db, result