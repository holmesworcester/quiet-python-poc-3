import json
import base64


def execute(input_data, identity, db):
    """
    Returns an invite-link containing this peer, for sharing out-of-band
    """
    # Get the identity's public key
    pubkey = input_data.get("pubkey")
    if not pubkey:
        # Try to find it in identities
        identities = db.get('state', {}).get('identities', [])
        for id_data in identities:
            if id_data.get('name') == identity:
                pubkey = id_data.get('pubkey')
                break
    
    if not pubkey:
        return {
            "return": "Error: No pubkey found for identity",
            "error": "Missing pubkey"
        }
    
    # Create invite data
    invite_data = {
        "peer": pubkey,
        "name": input_data.get("name", identity)
    }
    
    # Encode as base64 for easy sharing
    invite_json = json.dumps(invite_data, sort_keys=True)
    invite_link = f"message-via-tor://invite/{base64.urlsafe_b64encode(invite_json.encode()).decode()}"
    
    return {
        "return": "Invite link created",
        "invite_link": invite_link,
        "invite_data": invite_data
    }