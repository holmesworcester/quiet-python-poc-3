def project(db, envelope, time_now_ms):
    """
    Project user events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'users' not in db['state']:
        db['state']['users'] = []
    
    if 'blocked' not in db['state']:
        db['state']['blocked'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'user':
        return db
    
    user_id = data.get('id')
    network_id = data.get('network_id')
    pubkey = data.get('pubkey')
    name = data.get('name')
    invite_id = data.get('invite_id')
    
    if not all([user_id, network_id, pubkey, name]):
        return db
    
    # Check if user already exists
    for existing in db['state']['users']:
        if existing.get('id') == user_id:
            return db
    
    # Validate user
    is_valid = False
    blocked_reason = None
    
    # Check if user is network creator
    network = db['state'].get('network', {})
    if network.get('creator_pubkey') == pubkey:
        is_valid = True
    elif invite_id:
        # Check if invite exists
        invites = db['state'].get('invites', [])
        invite_found = False
        for invite in invites:
            if invite.get('id') == invite_id:
                invite_found = True
                is_valid = True
                break
        
        if not invite_found:
            blocked_reason = f"Invite {invite_id} not found"
    else:
        blocked_reason = "User is not network creator and has no valid invite"
    
    if not is_valid:
        # Block this user
        blocked = db['state']['blocked']
        blocked.append({
            'event_id': user_id,
            'blocked_by': invite_id or 'invalid_user',
            'reason': blocked_reason
        })
        db['state']['blocked'] = blocked
        return db
    
    # Add user
    user_data = {
        'id': user_id,
        'network_id': network_id,
        'pubkey': pubkey,
        'name': name
    }
    
    if invite_id:
        user_data['invite_id'] = invite_id
    
    state = db['state']
    state['users'].append(user_data)
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Try to unblock any events waiting on this user
    unblock(db, user_id)
    
    return db

def unblock(db, event_id):
    """
    Unblock events that were waiting for this event
    """
    if 'blocked' not in db.get('state', {}):
        return
    
    blocked = db['state']['blocked']
    remaining_blocked = []
    
    for blocked_event in blocked:
        if blocked_event.get('blocked_by') == event_id:
            # This event can potentially be unblocked
            # In a real implementation, we would re-process the event
            pass
        else:
            remaining_blocked.append(blocked_event)
    
    db['state']['blocked'] = remaining_blocked