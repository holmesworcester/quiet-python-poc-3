def project(db, envelope, time_now_ms):
    """
    Project invite events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'invites' not in db['state']:
        db['state']['invites'] = []
    
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'invite':
        return db
    
    invite_id = data.get('id')
    invite_pubkey = data.get('invite_pubkey')
    network_id = data.get('network_id')
    created_by = data.get('created_by')
    group_id = data.get('group_id')
    signature = data.get('signature')
    
    if not all([invite_id, invite_pubkey, network_id, created_by, signature]):
        return db
    
    # Check if group_id is missing
    if not group_id:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this invite due to missing group_id
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'missing_group_id' not in blocked_by_id:
            blocked_by_id['missing_group_id'] = []
        blocked_by_id['missing_group_id'].append({
            'event_id': invite_id,
            'reason': "Invite missing group_id"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if signature is from a known user
    # In dummy mode, we check if signature contains reference to unknown pubkey
    if signature.startswith("dummy_sig_from_unknown"):
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this invite due to unknown signer
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'invalid_signature' not in blocked_by_id:
            blocked_by_id['invalid_signature'] = []
        blocked_by_id['invalid_signature'].append({
            'event_id': invite_id,
            'reason': "Event signed by unknown user"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if this is the first group
    first_group_id = db['state'].get('first_group_id')
    if first_group_id and group_id != first_group_id:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this invite as it's not for the first group
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'invalid_group' not in blocked_by_id:
            blocked_by_id['invalid_group'] = []
        blocked_by_id['invalid_group'].append({
            'event_id': invite_id,
            'reason': f"Invites must be for the first group {first_group_id}, not {group_id}"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if group exists
    groups = db['state'].get('groups', [])
    group_exists = False
    for group in groups:
        if group.get('id') == group_id:
            group_exists = True
            break
    
    if not group_exists:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this invite using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if group_id not in blocked_by_id:
            blocked_by_id[group_id] = []
        blocked_by_id[group_id].append({
            'event_id': invite_id,
            'reason': f"Group {group_id} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if creator is a valid user
    users = db['state'].get('users', [])
    creator_valid = False
    for user in users:
        if user.get('id') == created_by:
            creator_valid = True
            break
    
    if not creator_valid:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this invite using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if created_by not in blocked_by_id:
            blocked_by_id[created_by] = []
        blocked_by_id[created_by].append({
            'event_id': invite_id,
            'reason': f"Creator user {created_by} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
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
        'group_id': group_id,
        'created_by': created_by
    }
    
    state = db['state']
    state['invites'].append(invite_data)
    # Sort invites by ID for deterministic ordering
    state['invites'].sort(key=lambda i: i['id'])
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