def project(db, envelope, time_now_ms, current_identity):
    """
    Projects decrypted but unrecognized event types to unknown_events table.
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'unknown_events' not in db['state']:
        db['state']['unknown_events'] = []
    
    # Add to unknown events table
    unknown_entry = {
        'data': envelope.get('data'),
        'metadata': envelope.get('metadata', {}),
        'timestamp': envelope.get('metadata', {}).get('receivedAt', time_now_ms)
    }
    
    db['state']['unknown_events'].append(unknown_entry)
    
    return db