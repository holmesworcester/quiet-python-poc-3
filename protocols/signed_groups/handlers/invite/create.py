import hashlib
import json
import base64

def execute(params, db):
    """
    Creates an invite link for the network
    """
    identity_id = params.get('identityId')
    
    if not identity_id:
        raise ValueError("identityId is required")
    
    state = db.get('state', {})
    
    # Find identity
    identities = state.get('identities', [])
    identity = None
    for i in identities:
        if i['pubkey'] == identity_id:
            identity = i
            break
    
    if not identity:
        raise ValueError(f"Identity {identity_id} not found")
    
    # Find user for this identity
    users = state.get('users', [])
    user = None
    for u in users:
        if u['pubkey'] == identity_id:
            user = u
            break
    
    if not user:
        raise ValueError(f"User for identity {identity_id} not found")
    
    network = state.get('network')
    if not network:
        raise ValueError("No network found")
    
    # Find the first group (required for invites)
    groups = state.get('groups', [])
    if not groups:
        raise ValueError("No groups found - at least one group is required")
    
    # Use the first group
    first_group = groups[0]
    
    # Generate invite secret and derive public key
    import time
    time_ms = int(time.time() * 1000)
    secret_data = f"{user['id']}:{time_ms}"
    invite_secret = "invite_secret_" + hashlib.sha256(secret_data.encode()).hexdigest()[:16]
    invite_pubkey = "invite_pub_" + hashlib.sha256(invite_secret.encode()).hexdigest()[:16]
    invite_id = hashlib.sha256(invite_pubkey.encode()).hexdigest()[:16]
    
    # Create dummy signature
    signature_data = f"invite:{invite_id}:{user['id']}"
    signature = "dummy_sig_" + hashlib.sha256(signature_data.encode()).hexdigest()[:8]
    
    # Create invite event
    invite_event = {
        'type': 'invite',
        'id': invite_id,
        'invite_pubkey': invite_pubkey,
        'network_id': network['id'],
        'group_id': first_group['id'],
        'created_by': user['id'],
        'signature': signature
    }
    
    # Create invite link data (include group_id in link)
    invite_data = {
        'invite_secret': invite_secret,
        'network_id': network['id'],
        'network_name': network['name'],
        'group_id': first_group['id']
    }
    
    # Encode invite link
    invite_json = json.dumps(invite_data)
    invite_b64 = base64.b64encode(invite_json.encode()).decode()
    invite_link = f"signed-groups://invite/{invite_b64}"
    
    return {
        'api_response': {
            'inviteLink': invite_link,
            'inviteId': invite_id
        },
        'newEvents': [invite_event]
    }