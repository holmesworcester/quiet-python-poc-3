# SQL Transactions Implementation Plan

## Overview
This plan outlines how to implement proper SQL transaction management in the event-driven framework, ensuring each event is processed atomically with full rollback capability on errors.

## Current State Analysis

### Problems Identified
1. **No transaction boundaries**: Each db write commits immediately via `PersistentDict.__setitem__`
2. **Mixed state modification patterns**: 
   - Projectors modify state (correct)
   - Commands directly modify state (some correct, some incorrect)
   - Core framework modifies state directly in several places
3. **No rollback capability**: If a projector fails halfway, partial state remains
4. **No event deduplication**: Same event can be processed multiple times

### Direct State Modifications Found
- **Handler commands**: 8 files directly modify `db['state']` or `db['outgoing']`
- **Core framework**: test_runner.py contains protocol-specific logic for permutation tests
- **Infrastructure vs Domain State**: Commands modify queues (`outgoing`/`incoming`) which are transport infrastructure, not domain events

## Proposed Solution

### Key Architectural Decision: Infrastructure vs Domain State

We distinguish between two types of state:
1. **Domain State**: Business events that should go through projectors (e.g., message created, identity joined)
2. **Infrastructure State**: Transport/queue operations that can be modified directly (e.g., outgoing/incoming queues)

This acknowledges that not everything needs to be an event - transport queues are operational infrastructure, not domain events.

### Formalizing Infrastructure State

Currently, protocols only use two infrastructure queues:
- `state.outgoing` - Queue of messages waiting to be sent
- `state.incoming` - Queue of received messages to process

For now, we can hardcode these as infrastructure state in the framework, with the option to make it configurable later if protocols need additional infrastructure state:

```python
# core/constants.py
INFRASTRUCTURE_PATHS = [
    'state.outgoing',
    'state.incoming',
    'incoming',  # Some protocols use top-level incoming
    'blocked',   # Framework-managed error queue
]
```

If future protocols need custom infrastructure state, we can add a `protocol.yaml` configuration file at that time.

### Phase 1: Add Transaction Support to PersistentDict

```python
# core/db.py modifications
class PersistentDict:
    def begin_transaction(self):
        """Start a new transaction, disable auto-commit"""
        self._in_transaction = True
        self._transaction_cache = {}
        
    def commit(self):
        """Commit all pending changes"""
        if not self._in_transaction:
            return
            
        # Apply all changes from transaction cache
        for key, value in self._transaction_cache.items():
            self._commit_change(key, value)
        
        self._conn.commit()
        self._cache.update(self._transaction_cache)
        self._transaction_cache = {}
        self._in_transaction = False
        
    def rollback(self):
        """Discard all pending changes"""
        if not self._in_transaction:
            return
            
        self._conn.rollback()
        self._transaction_cache = {}
        self._in_transaction = False
        
    def __setitem__(self, key, value):
        if self._in_transaction:
            # Store in transaction cache instead of committing
            self._transaction_cache[key] = value
        else:
            # Current behavior: immediate commit
            self._commit_change(key, value)
```

### Phase 2: Modify handle.py for Transaction Management

```python
# core/handle.py modifications
def handle(envelope, db):
    """Process a single event within a transaction"""
    
    # Start transaction
    db.begin_transaction()
    
    try:
        # 1. Check for duplicate event (deduplication)
        event_id = envelope.get('metadata', {}).get('eventId')
        if event_id and _event_already_processed(db, event_id):
            db.rollback()
            return db
        
        # 2. Persist event to event store FIRST
        _persist_event_to_store(envelope, db)
        
        # 3. Route to appropriate handler's projector
        handler = _find_handler(envelope)
        if handler:
            db = handler.project(envelope, db)
        else:
            # Add to unknown events through projector
            db = _project_unknown_event(envelope, db)
        
        # 4. Commit if successful
        db.commit()
        
    except Exception as e:
        # 5. Rollback on any error
        db.rollback()
        
        # Create error event (in new transaction)
        error_event = {
            'type': 'handle.error',
            'originalEvent': envelope,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }
        
        # Process error event in separate transaction
        db.begin_transaction()
        try:
            _persist_event_to_store(error_event, db)
            db = _project_error_event(error_event, db)
            db.commit()
        except:
            db.rollback()
            # Log critical failure
            
        raise  # Re-raise original error
    
    return db

def _event_already_processed(db, event_id):
    """Check if event has been processed"""
    # Query event store for this eventId
    cursor = db._conn.cursor()
    cursor.execute(
        "SELECT 1 FROM _event_store WHERE data LIKE ?",
        (f'%"eventId":"{event_id}"%',)
    )
    return cursor.fetchone() is not None

def _persist_event_to_store(envelope, db):
    """Add event to event store"""
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
```

### Phase 3: Handle Infrastructure State Within Transactions

For infrastructure state (queues), allow direct modification within transactions:

```python
# command.py modifications
from core.constants import INFRASTRUCTURE_PATHS

def run_command(command_name, handler_name, protocol_path, db, **kwargs):
    """Run command with transaction support"""
    
    db.begin_transaction()
    try:
        # Run the command
        result = command_module.run(db, **kwargs)
        
        # Process any domain events
        if 'newEvents' in result:
            for event_data in result['newEvents']:
                envelope = create_envelope(event_data)
                db = handle(envelope, db)
        
        # Allow direct infrastructure updates
        if 'db' in result:
            for key, value in result['db'].items():
                if is_infrastructure_path(key):
                    # Direct update allowed for infrastructure
                    apply_db_update(db, key, value)
                else:
                    # Domain state should go through events
                    raise ValueError(
                        f"Direct modification of domain state '{key}' not allowed. "
                        f"Must use events for domain state changes."
                    )
        
        db.commit()
        return result
        
    except Exception as e:
        db.rollback()
        raise

def is_infrastructure_path(path):
    """Check if a path is infrastructure state"""
    # Handle nested paths within state
    if path == 'state' and isinstance(value, dict):
        # Check each key within state
        return all(k in ['outgoing', 'incoming'] for k in value.keys())
    
    # Check against known infrastructure paths
    for infra_path in INFRASTRUCTURE_PATHS:
        if path == infra_path or path.startswith(infra_path + '.'):
            return True
    return False
```

This allows commands to continue modifying queues directly while ensuring atomicity:

```python
# Example: message/create.py can continue to do:
db['state']['outgoing'].append(outgoing_message)
# This is OK because outgoing is infrastructure, not a domain event
```

## Implementation Steps

### Week 1: Core Transaction Support
1. Implement transaction methods in PersistentDict
2. Add comprehensive tests for transaction behavior
3. Ensure backward compatibility (auto-commit when not in transaction)

### Week 2: Event Processing 
1. Modify handle.py to use transactions
2. Implement event deduplication
3. Add error event handling
4. Test rollback scenarios

### Week 3: Infrastructure State Validation
1. Create core/constants.py with hardcoded infrastructure paths
2. Modify command.py to validate infrastructure vs domain state
3. Update error messages to be helpful
4. Test with existing commands that modify queues

### Week 4: Framework Integration
1. Update test_runner.py to remove protocol-specific logic
2. Ensure api.py uses transactions for all updates
3. Document the infrastructure state pattern
4. Comprehensive integration testing

## Testing Strategy

1. **Unit tests**: Transaction commit/rollback behavior
2. **Integration tests**: Event processing with failures
3. **Concurrency tests**: Multiple events processed simultaneously
4. **Recovery tests**: Database state after crashes
5. **Migration tests**: Ensure existing data still works

## Rollback Plan

1. Keep current PersistentDict behavior as default
2. Add feature flag for transaction mode
3. Gradual rollout by protocol
4. Full rollback capability if issues found

## Success Criteria

1. Every event processed atomically
2. Failed projections leave no partial state
3. Duplicate events automatically skipped
4. Domain state changes only through events
5. Infrastructure state (queues) can be modified directly within transactions
6. Clear separation between domain and infrastructure concerns

## Open Questions

1. Should we support batch transactions for performance?
2. How to handle long-running projections?
3. Should we add transaction timeouts?
4. When protocols need more infrastructure state, how do we extend the system?
5. Should we log/audit infrastructure state changes differently than domain events?