import json
import base64
import hashlib

def execute(params, db):
    """
    Join network using invite link
    """
    identity_id = params.get('identityId')
    invite_link = params.get('inviteLink')
    
    if not identity_id or not invite_link:
        raise ValueError("identityId and inviteLink are required")
    
    # Parse invite link
    if not invite_link.startswith("signed-groups://invite/"):
        raise ValueError("Invalid invite link format")
    
    invite_b64 = invite_link[23:]  # Remove prefix
    try:
        invite_json = base64.b64decode(invite_b64).decode()
        invite_data = json.loads(invite_json)
    except:
        raise ValueError("Invalid invite link encoding")
    
    invite_secret = invite_data.get('invite_secret')
    network_id = invite_data.get('network_id')
    group_id = invite_data.get('group_id')
    
    if not invite_secret or not network_id or not group_id:
        raise ValueError("Invalid invite data - missing required fields")
    
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
    
    # Derive invite pubkey from secret
    invite_pubkey = "invite_pub_" + hashlib.sha256(invite_secret.encode()).hexdigest()[:16]
    
    # Find matching invite
    invites = state.get('invites', [])
    invite = None
    for inv in invites:
        if inv.get('invite_pubkey') == invite_pubkey:
            invite = inv
            break
    
    if not invite:
        raise ValueError("Invite not found or invalid")
    
    # Generate user ID
    user_id = hashlib.sha256(f"{network_id}:{identity_id}:{invite['id']}".encode()).hexdigest()[:16]
    
    # Create dummy signatures
    inv_sig_data = f"{invite_secret}:{user_id}"
    invite_signature = "dummy_inv_sig_" + hashlib.sha256(inv_sig_data.encode()).hexdigest()[:8]
    sig_data = f"user:{user_id}:{identity_id}"
    signature = "dummy_sig_" + hashlib.sha256(sig_data.encode()).hexdigest()[:8]
    
    # Create user event
    user_event = {
        'type': 'user',
        'id': user_id,
        'network_id': network_id,
        'group_id': group_id,  # From invite
        'pubkey': identity_id,
        'name': identity['name'],
        'invite_id': invite['id'],
        'invite_signature': invite_signature,
        'signature': signature
    }
    
    return {
        'api_response': {
            'userId': user_id,
            'networkId': network_id
        },
        'newEvents': [user_event]
    }