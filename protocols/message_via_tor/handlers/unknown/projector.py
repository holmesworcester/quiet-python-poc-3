def project(db, envelope, time_now_ms):
    """
    Projects decrypted but unrecognized event types to unknown_events table.
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'unknown_events' not in db['state']:
        state = db['state']
        state['unknown_events'] = []
        db['state'] = state
    
    # Add to unknown events table
    unknown_entry = {
        'data': envelope.get('data'),
        'metadata': envelope.get('metadata', {}),
        'timestamp': envelope.get('metadata', {}).get('receivedAt', time_now_ms)
    }
    
    # Get state, modify it, and reassign to trigger persistence
    state = db['state']
    state['unknown_events'].append(unknown_entry)
    db['state'] = state  # Trigger persistence!
    
    # Store in eventStore
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    # Get eventStore, modify, and reassign
    event_store = db['eventStore']
    event_store.append(envelope)  # Store full envelope
    db['eventStore'] = event_store
    
    return db