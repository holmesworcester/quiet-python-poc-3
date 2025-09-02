def project(db, envelope, time_now_ms):
    """
    Project user events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'users' not in db['state']:
        db['state']['users'] = []
    
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'user':
        return db
    
    user_id = data.get('id')
    network_id = data.get('network_id')
    pubkey = data.get('pubkey')
    name = data.get('name')
    invite_id = data.get('invite_id')
    group_id = data.get('group_id')
    signature = data.get('signature')
    
    if not all([user_id, network_id, pubkey, name, signature]):
        return db
    
    # First check if signature is from a known user (special case for first user)
    # In dummy mode, we check if signature contains reference to unknown pubkey
    if signature.startswith("dummy_sig_from_unknown"):
        # Check if this is the first user (network creator)
        network = db['state'].get('network', {})
        if network.get('creator_pubkey') != pubkey:
            # Not the network creator, so block it
            if 'eventStore' not in db:
                db['eventStore'] = []
            db['eventStore'].append(envelope)
            
            # Block this user due to unknown signer
            blocked_by_id = db['state'].get('blocked_by_id', {})
            if 'invalid_signature' not in blocked_by_id:
                blocked_by_id['invalid_signature'] = []
            blocked_by_id['invalid_signature'].append({
                'event_id': user_id,
                'reason': "Event signed by unknown user"
            })
            db['state']['blocked_by_id'] = blocked_by_id
            
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
        # Network creator doesn't need group_id
    elif invite_id:
        # Users joining via invite MUST have group_id
        if not group_id:
            # Store event in eventStore even when blocked
            if 'eventStore' not in db:
                db['eventStore'] = []
            db['eventStore'].append(envelope)
            
            # Block this user due to missing group_id
            blocked_by_id = db['state'].get('blocked_by_id', {})
            if 'missing_group_id' not in blocked_by_id:
                blocked_by_id['missing_group_id'] = []
            blocked_by_id['missing_group_id'].append({
                'event_id': user_id,
                'reason': "User missing group_id"
            })
            db['state']['blocked_by_id'] = blocked_by_id
            
            return db
        
        # Check if user is joining the first group
        first_group_id = db['state'].get('first_group_id')
        if first_group_id and group_id != first_group_id:
            # Store event in eventStore even when blocked
            if 'eventStore' not in db:
                db['eventStore'] = []
            db['eventStore'].append(envelope)
            
            # Block this user as they're not joining the first group
            blocked_by_id = db['state'].get('blocked_by_id', {})
            if 'invalid_group' not in blocked_by_id:
                blocked_by_id['invalid_group'] = []
            blocked_by_id['invalid_group'].append({
                'event_id': user_id,
                'reason': f"Users must join the first group {first_group_id}, not {group_id}"
            })
            db['state']['blocked_by_id'] = blocked_by_id
            
            return db
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
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this user using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        blocker_id = invite_id or 'invalid_user'
        if blocker_id not in blocked_by_id:
            blocked_by_id[blocker_id] = []
        blocked_by_id[blocker_id].append({
            'event_id': user_id,
            'reason': blocked_reason
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Add user
    user_data = {
        'id': user_id,
        'network_id': network_id,
        'pubkey': pubkey,
        'name': name
    }
    
    if group_id:
        user_data['group_id'] = group_id
    
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
    import os
    if os.environ.get("TEST_MODE"):
        print(f"[user.projector] Added user {user_id}, calling unblock")
    unblock(db, user_id)
    
    return db

def unblock(db, event_id):
    """
    Mark events that were waiting for this event as ready to unblock
    """
    import os
    state = db.get('state', {})
    blocked_by_id = state.get('blocked_by_id', {})
    ready_to_unblock = state.get('ready_to_unblock', {})
    
    if os.environ.get("TEST_MODE"):
        print(f"[user.unblock] Looking for events blocked by {event_id}")
        print(f"[user.unblock] blocked_by_id: {blocked_by_id}")
    
    # Find all events blocked by this event_id
    if event_id in blocked_by_id:
        for blocked_event in blocked_by_id[event_id]:
            ready_to_unblock[blocked_event['event_id']] = True
            if os.environ.get("TEST_MODE"):
                print(f"[user.unblock] Marking {blocked_event['event_id']} as ready_to_unblock")
    
    db['state']['ready_to_unblock'] = ready_to_unblock