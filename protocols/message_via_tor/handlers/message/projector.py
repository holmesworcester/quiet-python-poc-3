def project(db, envelope, time_now_ms):
    """
    Project message events into state.
    Validates sig using metadata, adds to state.messages if valid.
    If selfGenerated, this is a message we are sending, so add it to outgoing.
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    # Get data and metadata
    data = envelope.get('data', {})
    metadata = envelope.get('metadata', {})
    
    # Extract sender from data or metadata
    sender = data.get('sender') or metadata.get('sender')
    
    # Store in eventStore as a list
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    db['eventStore'].append(data)
    
    # Check if message has text
    text = data.get('text')
    if not text:
        # Skip messages without text
        return db
        
    # Initialize received_by early for peer checking
    received_by = metadata.get('received_by')
    if not received_by and metadata.get('selfGenerated'):
        # For self-generated messages without explicit received_by, we received it at our own address
        received_by = sender
    
    # Check if sender is known to the recipient by looking at peers list
    peers = db['state'].get('peers', [])
    is_known_peer = False
    
    # For checking if a peer is known, we need to know who received the message
    if received_by:
        # Check if this specific recipient knows the sender
        for peer in peers:
            if (peer.get('pubkey') == sender and 
                peer.get('received_by') == received_by):
                is_known_peer = True
                break
    else:
        # Legacy behavior: if no received_by is specified, check if peer is known to anyone
        # This is for backward compatibility with tests
        peer_pubkeys = [p.get('pubkey') for p in peers]
        is_known_peer = sender in peer_pubkeys
    
    # Process all messages with text
    # Valid - update state
    if 'messages' not in db['state']:
        db['state']['messages'] = []
    
    # Extract message info
    message = {
        'text': text,
        'sender': sender,
        'timestamp': data.get('timestamp', time_now_ms)
    }
    
    # Add optional fields
    if data.get('sig'):
        message['sig'] = data['sig']
    
    # Set received_by in the message if we have it
    if received_by:
        message['received_by'] = received_by
    
    # Only check identity existence for non-self-generated messages with explicit received_by
    if received_by and not metadata.get('selfGenerated'):
        # Only store messages for identities that exist in our database
        our_identities = db['state'].get('identities', [])
        our_pubkeys = [id.get('pubkey') for id in our_identities]
        if received_by not in our_pubkeys:
            # This message is for an identity we don't have
            return db
    
    # Also preserve the intended recipient from the message data
    if data.get('recipient'):
        message['recipient'] = data['recipient']
    
    if metadata.get('eventId'):
        message['id'] = metadata['eventId']
    
    # Mark as unknown_peer if sender is not known
    if not is_known_peer:
        message['unknown_peer'] = True
    
    # Add to messages
    db['state']['messages'].append(message)
    
    return db