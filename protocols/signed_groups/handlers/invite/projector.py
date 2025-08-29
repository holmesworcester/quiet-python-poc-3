def project(db, envelope, time_now_ms):
    """
    Project invite events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'invites' not in db['state']:
        db['state']['invites'] = []
    
    if 'blocked' not in db['state']:
        db['state']['blocked'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'invite':
        return db
    
    invite_id = data.get('id')
    invite_pubkey = data.get('invite_pubkey')
    network_id = data.get('network_id')
    created_by = data.get('created_by')
    
    if not all([invite_id, invite_pubkey, network_id, created_by]):
        return db
    
    # Check if creator is a valid user
    users = db['state'].get('users', [])
    creator_valid = False
    for user in users:
        if user.get('id') == created_by:
            creator_valid = True
            break
    
    if not creator_valid:
        # Block this invite - creator not found
        blocked = db['state']['blocked']
        blocked.append({
            'event_id': invite_id,
            'blocked_by': 'user_not_found',
            'reason': f"Creator user {created_by} not found"
        })
        db['state']['blocked'] = blocked
        return db
    
    # Check if invite already exists
    for existing in db['state']['invites']:
        if existing.get('id') == invite_id:
            return db
    
    # Add invite
    invite_data = {
        'id': invite_id,
        'invite_pubkey': invite_pubkey,
        'network_id': network_id,
        'created_by': created_by
    }
    
    state = db['state']
    state['invites'].append(invite_data)
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Try to unblock any events waiting on this invite
    unblock(db, invite_id)
    
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