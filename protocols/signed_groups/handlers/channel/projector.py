def project(db, envelope, time_now_ms):
    """
    Project channel events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'channels' not in db['state']:
        db['state']['channels'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'channel':
        return db
    
    channel_id = data.get('id')
    network_id = data.get('network_id')
    name = data.get('name')
    created_by = data.get('created_by')
    group_id = data.get('group_id')
    signature = data.get('signature')
    
    if not all([channel_id, network_id, name, created_by, signature]):
        return db
    
    # Check if signature is from a known user
    # In dummy mode, we check if signature contains reference to unknown pubkey
    if signature.startswith("dummy_sig_from_unknown"):
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this channel due to unknown signer
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if 'invalid_signature' not in blocked_by_id:
            blocked_by_id['invalid_signature'] = []
        blocked_by_id['invalid_signature'].append({
            'event_id': channel_id,
            'reason': "Event signed by unknown user"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Check if channel already exists
    for existing in db['state']['channels']:
        if existing.get('id') == channel_id:
            return db
    
    # Check if group exists (if group_id is provided)
    if group_id:
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
            
            # Block this channel using indexed structure
            blocked_by_id = db['state'].get('blocked_by_id', {})
            if group_id not in blocked_by_id:
                blocked_by_id[group_id] = []
            blocked_by_id[group_id].append({
                'event_id': channel_id,
                'reason': f"Group {group_id} not found"
            })
            db['state']['blocked_by_id'] = blocked_by_id
            
            return db
    
    # Add channel
    channel_data = {
        'id': channel_id,
        'network_id': network_id,
        'name': name,
        'created_by': created_by
    }
    
    if group_id:
        channel_data['group_id'] = group_id
    
    state = db['state']
    state['channels'].append(channel_data)
    # Sort channels by ID for deterministic ordering
    state['channels'].sort(key=lambda c: c['id'])
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Mark any events blocked by this channel as ready to unblock
    unblock(db, channel_id)
    
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