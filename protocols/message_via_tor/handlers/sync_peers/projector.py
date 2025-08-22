def project(db, envelope, time_now_ms, current_identity):
    """
    Validates sync request and sends all peer events to requester
    """
    # Get data from envelope
    data = envelope.get('data', {})
    
    if data.get('type') != 'sync_peers':
        return db
    
    sender = data.get('sender')
    if not sender:
        return db
    
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'outgoing' not in db['state']:
        db['state']['outgoing'] = []
    
    # Get all peer events from eventStore and send to requester
    event_store = db.get('eventStore', {})
    
    for peer_pubkey, events in event_store.items():
        for event in events:
            if event.get('type') == 'peer':
                # Create outgoing envelope for this peer event
                outgoing = {
                    'recipient': sender,
                    'data': event
                }
                db['state']['outgoing'].append(outgoing)
    
    # Store the sync request in eventStore
    if 'eventStore' not in db:
        db['eventStore'] = {}
    
    sync_key = f"sync-peers-{sender}"
    if sync_key not in db['eventStore']:
        db['eventStore'][sync_key] = []
    
    db['eventStore'][sync_key].append(data)
    
    return db