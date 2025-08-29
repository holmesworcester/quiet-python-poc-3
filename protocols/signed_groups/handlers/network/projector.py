def project(db, envelope, time_now_ms):
    """
    Project network events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'network':
        return db
    
    network_id = data.get('id')
    name = data.get('name')
    creator_pubkey = data.get('creator_pubkey')
    
    if not network_id or not name or not creator_pubkey:
        return db
    
    # Store network info
    network_data = {
        'id': network_id,
        'name': name,
        'creator_pubkey': creator_pubkey
    }
    
    state = db['state']
    state['network'] = network_data
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    return db