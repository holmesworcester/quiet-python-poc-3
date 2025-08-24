def project(db, envelope, time_now_ms):
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
    event_store = db.get('eventStore', [])
    
    for event in event_store:
        event_type = event.get('type')
        if event_type == 'peer':
            # Create outgoing envelope for this event
            outgoing = {
                'recipient': sender,
                'data': event
            }
            db['state']['outgoing'].append(outgoing)
    
    # Store the sync request in eventStore
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    # Append the event data directly
    db['eventStore'].append(data)
    
    return db