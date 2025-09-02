def project(db, envelope, time_now_ms):
    """
    Project message events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'messages' not in db['state']:
        db['state']['messages'] = []
    
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'message':
        return db
    
    message_id = data.get('id')
    channel_id = data.get('channel_id')
    author_id = data.get('author_id')
    peer_id = data.get('peer_id')
    user_id = data.get('user_id')
    content = data.get('content')
    text = data.get('text')
    signature = data.get('signature')
    
    # Use content or text (docs says "text" but tests use "content")
    if not content and text:
        content = text
    
    if not all([message_id, channel_id, author_id, content, signature]):
        return db
    
    # Check if peer_id is missing
    if not peer_id:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this message due to missing peer_id
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'missing_fields' not in blocked_by_id:
            blocked_by_id['missing_fields'] = []
        blocked_by_id['missing_fields'].append({
            'event_id': message_id,
            'reason': "Message missing peer_id"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if peer_id is valid - it must either match user_id or be a linked device
    peer_valid = False
    
    if peer_id == user_id:
        # Direct match - user posting from their main device
        peer_valid = True
    else:
        # Check if peer is linked to the user
        links = db['state'].get('links', [])
        for link in links:
            if link.get('peer_id') == peer_id and link.get('user_id') == user_id:
                peer_valid = True
                break
    
    if not peer_valid:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this message - peer not linked to user
        blocked_by_id = db['state'].get('blocked_by_id', {})
        # Use peer_id as the blocker so it can be unblocked when link is created
        if peer_id not in blocked_by_id:
            blocked_by_id[peer_id] = []
        blocked_by_id[peer_id].append({
            'event_id': message_id,
            'reason': f"Peer {peer_id} not linked to user {user_id}"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Verify signature matches peer_id
    # In dummy mode, we check if signature indicates it was signed by the peer
    if signature.startswith("dummy_sig_signed_by_"):
        # Extract who signed it from the dummy signature
        signer_id = signature.replace("dummy_sig_signed_by_", "")
        if signer_id != peer_id:
            # Store event in eventStore even when blocked
            if 'eventStore' not in db:
                db['eventStore'] = []
            db['eventStore'].append(envelope)
            
            # Block this message due to signature mismatch
            blocked_by_id = db['state'].get('blocked_by_id', {})
            if 'signature_mismatch' not in blocked_by_id:
                blocked_by_id['signature_mismatch'] = []
            blocked_by_id['signature_mismatch'].append({
                'event_id': message_id,
                'reason': f"Signature does not match claimed peer {peer_id}"
            })
            db['state']['blocked_by_id'] = blocked_by_id
            
            return db
    elif signature.startswith("dummy_sig_from_unknown"):
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this message due to unknown signer
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'invalid_signature' not in blocked_by_id:
            blocked_by_id['invalid_signature'] = []
        blocked_by_id['invalid_signature'].append({
            'event_id': message_id,
            'reason': "Event signed by unknown user"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if message already exists (idempotency)
    for existing in db['state']['messages']:
        if existing.get('id') == message_id:
            return db
    
    # Check if author exists
    users = db['state'].get('users', [])
    author_found = False
    for user in users:
        if user.get('id') == author_id:
            author_found = True
            break
    
    if not author_found:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this message using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if author_id not in blocked_by_id:
            blocked_by_id[author_id] = []
        blocked_by_id[author_id].append({
            'event_id': message_id,
            'reason': f"Author {author_id} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if channel exists
    channels = db['state'].get('channels', [])
    channel = None
    for ch in channels:
        if ch.get('id') == channel_id:
            channel = ch
            break
    
    if not channel:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this message using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if channel_id not in blocked_by_id:
            blocked_by_id[channel_id] = []
        blocked_by_id[channel_id].append({
            'event_id': message_id,
            'reason': f"Channel {channel_id} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if channel has a group_id and validate membership
    if channel.get('group_id'):
        group_id = channel['group_id']
        
        # Find the group
        groups = db['state'].get('groups', [])
        group = None
        for g in groups:
            if g.get('id') == group_id:
                group = g
                break
        
        if group:
            # Check if author is a member of the group
            # Member if: 1) group creator, or 2) added to group
            is_member = False
            
            # Check if author is group creator
            if group.get('created_by') == author_id:
                is_member = True
            else:
                # Check if author was added to group
                adds = db['state'].get('adds', [])
                for add in adds:
                    if add.get('group_id') == group_id and add.get('user_id') == author_id:
                        is_member = True
                        break
            
            if not is_member:
                # Store event in eventStore even when blocked
                if 'eventStore' not in db:
                    db['eventStore'] = []
                db['eventStore'].append(envelope)
                
                # Block this message due to group membership
                blocked_by_id = db['state'].get('blocked_by_id', {})
                if 'group_membership' not in blocked_by_id:
                    blocked_by_id['group_membership'] = []
                blocked_by_id['group_membership'].append({
                    'event_id': message_id,
                    'reason': f"Author {author_id} is not a member of group {group_id}"
                })
                db['state']['blocked_by_id'] = blocked_by_id
                
                return db
    
    # Add message
    message_data = {
        'id': message_id,
        'channel_id': channel_id,
        'author_id': author_id,
        'peer_id': peer_id,
        'user_id': user_id,
        'content': content
    }
    
    # Also add text if it was provided
    if text:
        message_data['text'] = text
    
    state = db['state']
    state['messages'].append(message_data)
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Mark any events blocked by this message as ready to unblock
    unblock(db, message_id)
    
    return db

def unblock(db, event_id):
    """
    Mark events that were waiting for this event as ready to unblock
    """
    state = db.get('state', {})
    blocked_by_id = state.get('blocked_by_id', {})
    ready_to_unblock = state.get('ready_to_unblock', {})
    
    # Find all events blocked by this event_id
    if event_id in blocked_by_id:
        for blocked_event in blocked_by_id[event_id]:
            ready_to_unblock[blocked_event['event_id']] = True
    
    db['state']['ready_to_unblock'] = ready_to_unblock