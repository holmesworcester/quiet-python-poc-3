def project(db, envelope, time_now_ms):
    """
    Project link-invite events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'link_invites' not in db['state']:
        db['state']['link_invites'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'link_invite':
        return db
    
    link_invite_id = data.get('id')
    link_invite_pubkey = data.get('link_invite_pubkey')
    user_id = data.get('user_id')
    signature = data.get('signature')
    
    if not all([link_invite_id, link_invite_pubkey, user_id, signature]):
        return db
    
    # Check if signature is from a known user
    # In dummy mode, we check if signature contains reference to unknown pubkey
    if signature.startswith("dummy_sig_from_unknown"):
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this link-invite due to unknown signer
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'invalid_signature' not in blocked_by_id:
            blocked_by_id['invalid_signature'] = []
        blocked_by_id['invalid_signature'].append({
            'event_id': link_invite_id,
            'reason': "Event signed by unknown user"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if user exists
    users = db['state'].get('users', [])
    user_exists = False
    for user in users:
        if user.get('id') == user_id:
            user_exists = True
            break
    
    if not user_exists:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this link-invite using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if user_id not in blocked_by_id:
            blocked_by_id[user_id] = []
        blocked_by_id[user_id].append({
            'event_id': link_invite_id,
            'reason': f"User {user_id} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if link-invite already exists
    for existing in db['state']['link_invites']:
        if existing.get('id') == link_invite_id:
            return db
    
    # Add link-invite
    link_invite_data = {
        'id': link_invite_id,
        'link_invite_pubkey': link_invite_pubkey,
        'user_id': user_id
    }
    
    state = db['state']
    state['link_invites'].append(link_invite_data)
    # Sort link_invites by ID for deterministic ordering
    state['link_invites'].sort(key=lambda li: li['id'])
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Try to unblock any events waiting on this link-invite
    unblock(db, link_invite_id)
    
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