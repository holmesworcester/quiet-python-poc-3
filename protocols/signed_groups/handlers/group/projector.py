def project(db, envelope, time_now_ms):
    """
    Project group events into state
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'groups' not in db['state']:
        db['state']['groups'] = []
    
    data = envelope.get('data', {})
    
    if data.get('type') != 'group':
        return db
    
    group_id = data.get('id')
    name = data.get('name')
    created_by = data.get('user_id')
    signature = data.get('signature')
    
    if not all([group_id, name, created_by, signature]):
        return db
    
    # Check if group already exists
    for existing in db['state']['groups']:
        if existing.get('id') == group_id:
            return db
    
    # Check if creator is a valid user and get their pubkey
    users = db['state'].get('users', [])
    creator_user = None
    for user in users:
        if user.get('id') == created_by:
            creator_user = user
            break
    
    if not creator_user:
        # Store event in eventStore even when blocked
        if 'eventStore' not in db:
            db['eventStore'] = []
        db['eventStore'].append(envelope)
        
        # Block this group using indexed structure
        blocked_by_id = db['state'].get('blocked_by_id', {})
        if created_by not in blocked_by_id:
            blocked_by_id[created_by] = []
        blocked_by_id[created_by].append({
            'event_id': group_id,
            'reason': f"Creator user {created_by} not found"
        })
        db['state']['blocked_by_id'] = blocked_by_id
        
        return db
    
    # Verify signature matches the creator's pubkey
    # In dummy mode, we check if signature indicates it was signed by the creator
    if signature.startswith("dummy_sig_signed_by_"):
        # Extract who signed it from the dummy signature
        signer_id = signature.replace("dummy_sig_signed_by_", "")
        if signer_id != created_by:
            # Store event in eventStore even when blocked
            if 'eventStore' not in db:
                db['eventStore'] = []
            db['eventStore'].append(envelope)
            
            # Block this group due to signature mismatch
            blocked_by_id = db['state'].get('blocked_by_id', {})
            if 'signature_mismatch' not in blocked_by_id:
                blocked_by_id['signature_mismatch'] = []
            blocked_by_id['signature_mismatch'].append({
                'event_id': group_id,
                'reason': f"Signature does not match claimed user {created_by}"
            })
            db['state']['blocked_by_id'] = blocked_by_id
            
            return db
    
    # Add group
    group_data = {
        'id': group_id,
        'name': name,
        'created_by': created_by
    }
    
    state = db['state']
    state['groups'].append(group_data)
    db['state'] = state
    
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    event_store = db['eventStore']
    event_store.append(envelope)
    db['eventStore'] = event_store
    
    # Try to unblock any events waiting on this group
    unblock(db, group_id)
    
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