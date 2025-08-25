def project(db, envelope, time_now_ms):
    """
    Validates peer has a public key and adds to projection
    Tracks which identity received this peer event
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'peers' not in db['state']:
        db['state']['peers'] = []
    
    # Get data and metadata from envelope
    data = envelope.get('data', {})
    metadata = envelope.get('metadata', {})
    
    # Validate peer event
    if data.get('type') != 'peer':
        return db
    
    pubkey = data.get('pubkey')
    if not pubkey:
        return db
    
    # Get which identity received this peer event
    received_by = metadata.get('received_by')
    if not received_by:
        # For self-generated peer events, use the sender's identity
        if metadata.get('selfGenerated'):
            # For self-generated peer events about oneself (like when creating an identity),
            # the peer IS the identity that should receive it
            # Check if this peer event is about an identity we just created
            peer_pubkey = data.get('pubkey')
            identities = db['state'].get('identities', [])
            
            # If this peer matches one of our identities, it's a self-peer event
            for identity in identities:
                if identity.get('pubkey') == peer_pubkey:
                    received_by = peer_pubkey
                    break
            
            # If still no received_by and we have identities, this might be a peer
            # being added manually, so use the first identity
            if not received_by and identities:
                received_by = identities[0].get('pubkey')
        
        if not received_by:
            # Can't determine which identity received this, skip
            return db
    
    # Check if this peer already exists for this specific identity
    for existing in db['state']['peers']:
        if (existing.get('pubkey') == pubkey and 
            existing.get('received_by') == received_by):
            # Already exists for this identity, skip
            return db
    
    # Add to peers with received_by field
    peer_data = {
        'pubkey': pubkey,
        'name': data.get('name', pubkey[:8]),
        'joined_via': data.get('joined_via', 'direct'),
        'added_at': time_now_ms,
        'received_by': received_by  # Track which identity knows this peer
    }
    
    # Get state, modify, and reassign to trigger persistence
    state = db['state']
    state['peers'].append(peer_data)
    
    # Check for messages from this peer marked as unknown_peer and update them
    # Only update messages that were received by the same identity
    messages = state.get('messages', [])
    for message in messages:
        if (message.get('sender') == pubkey and 
            message.get('received_by') == received_by and
            message.get('unknown_peer')):
            # Remove the unknown_peer flag
            del message['unknown_peer']
    
    db['state'] = state  # Trigger persistence!
    
    # Store in eventStore
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    # Get eventStore, modify, and reassign
    event_store = db['eventStore']
    event_store.append(data)
    db['eventStore'] = event_store  # Trigger persistence!
    
    return db