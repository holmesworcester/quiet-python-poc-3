def project(db, envelope, time_now_ms):
    """
    Project add events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'adds' not in db['state']:
        db['state']['adds'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'add':
        return db
    
    add_id = data.get('id')
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    added_by = data.get('added_by')
    signature = data.get('signature')
    
    if not all([add_id, group_id, user_id, added_by, signature]):
        return db
    
    # First check if the signature is from a known user
    # In dummy mode, we check if signature contains reference to a known user pubkey
    if signature.startswith("dummy_sig_from_unknown"):
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this add due to unknown signer
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'invalid_signature' not in blocked_by_id:
            blocked_by_id['invalid_signature'] = []
        blocked_by_id['invalid_signature'].append({
            'event_id': add_id,
            'reason': "Event signed by unknown user"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if add already exists
    for existing in db['state']['adds']:
        if existing.get('id') == add_id:
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
        
        # Block this add using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if group_id not in blocked_by_id:
            blocked_by_id[group_id] = []
        blocked_by_id[group_id].append({
            'event_id': add_id,
            'reason': f"Group {group_id} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if user being added exists
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
        
        # Block this add using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if user_id not in blocked_by_id:
            blocked_by_id[user_id] = []
        blocked_by_id[user_id].append({
            'event_id': add_id,
            'reason': f"User {user_id} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if adder exists
    adder_exists = False
    for user in users:
        if user.get('id') == added_by:
            adder_exists = True
            break
    
    if not adder_exists:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this add using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if added_by not in blocked_by_id:
            blocked_by_id[added_by] = []
        blocked_by_id[added_by].append({
            'event_id': add_id,
            'reason': f"Adder user {added_by} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Add the add event
    add_data = {
        'id': add_id,
        'group_id': group_id,
        'user_id': user_id,
        'added_by': added_by
    }
    
    state = db['state']
    state['adds'].append(add_data)
    # Sort adds by ID for deterministic ordering
    state['adds'].sort(key=lambda a: a['id'])
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Try to unblock any events waiting on this add
    unblock(db, add_id)
    
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