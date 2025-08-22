def project(db, envelope, time_now_ms, current_identity):
    """
    Validates peer has a public key and adds to projection
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'peers' not in db['state']:
        db['state']['peers'] = []
    
    # Get data from envelope
    data = envelope.get('data', {})
    
    # Validate peer event
    if data.get('type') != 'peer':
        return db
    
    pubkey = data.get('pubkey')
    if not pubkey:
        return db
    
    # Check if peer already exists
    for existing in db['state']['peers']:
        if existing.get('pubkey') == pubkey:
            # Already exists, skip
            return db
    
    # Add to peers
    peer_data = {
        'pubkey': pubkey,
        'name': data.get('name', pubkey[:8]),
        'joined_via': data.get('joined_via', 'direct'),
        'added_at': time_now_ms
    }
    
    db['state']['peers'].append(peer_data)
    
    # Store in eventStore
    if 'eventStore' not in db:
        db['eventStore'] = {}
    
    if pubkey not in db['eventStore']:
        db['eventStore'][pubkey] = []
    
    db['eventStore'][pubkey].append(data)
    
    return db