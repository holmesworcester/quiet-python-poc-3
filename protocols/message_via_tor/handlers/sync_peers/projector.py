def project(db, envelope, time_now_ms):
    """
    Validates sync request and sends peer events known by the receiving identity to requester
    """
    # Get data and metadata from envelope
    data = envelope.get('data', {})
    metadata = envelope.get('metadata', {})
    
    if data.get('type') != 'sync_peers':
        return db
    
    sender = data.get('sender')
    if not sender:
        return db
    
    # Get which identity received this sync request
    received_by = metadata.get('received_by')
    if not received_by:
        # Can't determine which identity received this, skip
        return db
    
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'outgoing' not in db['state']:
        state = db['state']
        state['outgoing'] = []
        db['state'] = state
    
    # Get peers known by the identity that received this sync request
    peers = db['state'].get('peers', [])
    known_peers = [p for p in peers if p.get('received_by') == received_by]
    
    # Send peer events for peers known by this identity
    if known_peers:
        state = db['state']
        for peer in known_peers:
            # Create peer event data to send
            peer_event = {
                'type': 'peer',
                'pubkey': peer.get('pubkey'),
                'name': peer.get('name')
            }
            
            # Create outgoing envelope for this event
            outgoing = {
                'recipient': sender,
                'data': peer_event
            }
            state['outgoing'].append(outgoing)
        db['state'] = state  # Trigger persistence!
    
    # Store the sync request in eventStore
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    # Get eventStore, modify it, and reassign to trigger persistence
    event_store = db['eventStore']
    event_store.append(data)
    db['eventStore'] = event_store  # Trigger persistence!
    
    return db