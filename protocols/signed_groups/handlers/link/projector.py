def project(db, envelope, time_now_ms):
    """
    Project link events into state - associates a new device (peer) with an existing user
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'links' not in db['state']:
        db['state']['links'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'link':
        return db
    
    link_id = data.get('id')
    peer_id = data.get('peer_id')
    user_id = data.get('user_id')
    link_invite_id = data.get('link_invite_id')
    link_invite_signature = data.get('link_invite_signature')
    signature = data.get('signature')
    
    if not all([link_id, peer_id, user_id, link_invite_id, link_invite_signature, signature]):
        return db
    
    # Verify signature is from peer_id (the new device)
    # In dummy mode, we check if signature indicates it was signed by the peer
    if signature.startswith("dummy_sig_signed_by_"):
        # Extract who signed it from the dummy signature
        signer_id = signature.replace("dummy_sig_signed_by_", "")
        if signer_id != peer_id:
            # Store event in eventStore even when blocked
            if 'eventStore' not in db:
                db['eventStore'] = []
            db['eventStore'].append(envelope)
            
            # Block this link due to signature mismatch
            blocked_by_id = db['state'].get('blocked_by_id', {})
            if 'signature_mismatch' not in blocked_by_id:
                blocked_by_id['signature_mismatch'] = []
            blocked_by_id['signature_mismatch'].append({
                'event_id': link_id,
                'reason': f"Signature does not match claimed peer {peer_id}"
            })
            db['state']['blocked_by_id'] = blocked_by_id
            
            return db
    
    # Check if link-invite exists
    link_invites = db['state'].get('link_invites', [])
    link_invite_found = False
    link_invite = None
    for li in link_invites:
        if li.get('id') == link_invite_id:
            link_invite_found = True
            link_invite = li
            break
    
    if not link_invite_found:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this link
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if link_invite_id not in blocked_by_id:
            blocked_by_id[link_invite_id] = []
        blocked_by_id[link_invite_id].append({
            'event_id': link_id,
            'reason': f"Link-invite {link_invite_id} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Verify that the user_id matches the link-invite's user_id
    if link_invite.get('user_id') != user_id:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this link
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'user_mismatch' not in blocked_by_id:
            blocked_by_id['user_mismatch'] = []
        blocked_by_id['user_mismatch'].append({
            'event_id': link_id,
            'reason': f"User ID {user_id} doesn't match link-invite user {link_invite.get('user_id')}"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if link already exists
    for existing in db['state']['links']:
        if existing.get('id') == link_id:
            return db
    
    # Add link
    link_data = {
        'id': link_id,
        'peer_id': peer_id,
        'user_id': user_id,
        'link_invite_id': link_invite_id
    }
    
    state = db['state']
    state['links'].append(link_data)
    # Sort links by ID for deterministic ordering
    state['links'].sort(key=lambda l: l['id'])
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Try to unblock any events waiting on this link
    unblock(db, link_id)
    # Also unblock any events waiting on this peer_id
    unblock(db, peer_id)
    
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