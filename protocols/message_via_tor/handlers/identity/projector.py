def project(db, envelope, time_now_ms, current_identity):
    """
    Project identity events into state
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'identities' not in db['state']:
        db['state']['identities'] = []
    
    # Get data from envelope
    data = envelope.get('data', {})
    
    # Validate identity event
    if data.get('type') != 'identity':
        return db
    
    pubkey = data.get('pubkey')
    privkey = data.get('privkey')
    name = data.get('name')
    
    if not pubkey or not privkey:
        return db
    
    # Check if identity already exists
    for existing in db['state']['identities']:
        if existing.get('pubkey') == pubkey:
            # Already exists, skip
            return db
    
    # Add to identities
    identity_data = {
        'pubkey': pubkey,
        'privkey': privkey,
        'name': name or pubkey[:8]
    }
    
    db['state']['identities'].append(identity_data)
    
    # Store in eventStore
    if 'eventStore' not in db:
        db['eventStore'] = {}
    
    if pubkey not in db['eventStore']:
        db['eventStore'][pubkey] = []
    
    db['eventStore'][pubkey].append(data)
    
    return db