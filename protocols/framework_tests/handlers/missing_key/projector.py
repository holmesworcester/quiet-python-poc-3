def project(db, envelope, time_now_ms):
    """
    Project missing key events into pending_missing_key state.
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'pending_missing_key' not in db['state']:
        state = db['state']
        state['pending_missing_key'] = []
        db['state'] = state
    
    # Extract metadata
    metadata = envelope.get('metadata', {})
    
    # Add to pending table
    pending_entry = {
        'envelope': envelope,
        'missingHash': metadata.get('missingHash'),
        'inNetwork': metadata.get('inNetwork', False),
        'timestamp': metadata.get('receivedAt', time_now_ms)
    }
    
    # Get state, modify it, and reassign to trigger persistence
    state = db['state']
    state['pending_missing_key'].append(pending_entry)
    db['state'] = state  # Trigger persistence!
    
    return db