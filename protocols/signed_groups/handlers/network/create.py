import hashlib

def execute(params, db):
    """
    Creates a new network and adds creator as first user
    """
    name = params.get('name')
    identity_id = params.get('identityId')
    
    if not name or not identity_id:
        raise ValueError("Network name and identityId are required")
    
    # Find identity
    state = db.get('state', {})
    identities = state.get('identities', [])
    identity = None
    for i in identities:
        if i['pubkey'] == identity_id:
            identity = i
            break
    
    if not identity:
        raise ValueError(f"Identity {identity_id} not found")
    
    # Generate network ID (hash of name + creator)
    network_id_data = f"{name}:{identity_id}".encode()
    network_id = hashlib.sha256(network_id_data).hexdigest()[:16]
    
    # Create network event (no signature needed - bootstrap event)
    network_event = {
        'type': 'network',
        'id': network_id,
        'name': name,
        'creator_pubkey': identity_id
    }
    
    # Create user event for creator (automatically valid as network creator)
    user_id = hashlib.sha256(f"{network_id}:{identity_id}".encode()).hexdigest()[:16]
    user_signature_data = f"user:{user_id}"
    user_signature = "dummy_sig_" + hashlib.sha256(user_signature_data.encode()).hexdigest()[:8]
    
    user_event = {
        'type': 'user',
        'id': user_id,
        'network_id': network_id,
        'pubkey': identity_id,
        'name': identity['name'],
        'signature': user_signature
    }
    
    return {
        'api_response': {
            'networkId': network_id,
            'name': name
        },
        'newEvents': [network_event, user_event]
    }