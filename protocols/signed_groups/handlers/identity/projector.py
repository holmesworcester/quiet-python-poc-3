def project(db, envelope, time_now_ms):
    """
    Project identity events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'identities' not in db['state']:
        db['state']['identities'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'identity':
        return db
    
    pubkey = data.get('pubkey')
    privkey = data.get('privkey')
    name = data.get('name')
    
    if not pubkey or not privkey:
        return db
    
    for existing in db['state']['identities']:
        if existing.get('pubkey') == pubkey:
            return db
    
    identity_data = {
        'pubkey': pubkey,
        'privkey': privkey,
        'name': name or pubkey[:8]
    }
    
    state = db['state']
    state['identities'].append(identity_data)
    # Sort identities by pubkey for deterministic ordering
    state['identities'].sort(key=lambda i: i['pubkey'])
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    return db