import json
import base64


def execute(input_data, identity, db):
    """
    Returns an invite-link containing this peer, for sharing out-of-band
    """
    # The identity parameter should be the pubkey/ID from the URL path
    # Find the full identity data
    identities = db.get('state', {}).get('identities', [])
    identity_data = None
    
    for id_data in identities:
        if id_data.get('pubkey') == identity:
            identity_data = id_data
            break
    
    if not identity_data:
        return {
            "api_response": {
                "return": "Error: Identity not found",
                "error": f"No identity found with pubkey {identity}"
            },
            "internal": {}
        }
    
    # Create invite data with peer info
    invite_data = {
        "peer": identity_data['pubkey'],
        "name": identity_data.get('name', 'Unknown')
    }
    
    # Encode as base64 for easy sharing
    invite_json = json.dumps(invite_data, sort_keys=True)
    invite_link = f"message-via-tor://invite/{base64.urlsafe_b64encode(invite_json.encode()).decode()}"
    
    return {
        "api_response": {
            "return": "Invite link created",
            "inviteLink": invite_link,  # Use camelCase for API consistency
            "inviteData": invite_data
        }
    }