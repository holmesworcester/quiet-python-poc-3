def project(db, envelope, time_now_ms):
    """
    Project missing key events into pending_missing_key state.
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'pending_missing_key' not in db['state']:
        db['state']['pending_missing_key'] = []
    
    # Extract metadata
    metadata = envelope.get('metadata', {})
    
    # Add to pending table
    pending_entry = {
        'envelope': envelope,
        'missingHash': metadata.get('missingHash'),
        'inNetwork': metadata.get('inNetwork', False),
        'timestamp': metadata.get('receivedAt', time_now_ms)
    }
    
    db['state']['pending_missing_key'].append(pending_entry)
    
    return db