import json
import base64


def execute(input_data, identity, db):
    """
    Consumes a valid invite link, creates a peer event for the peer in invite
    """
    invite_link = input_data.get("invite_link", "")
    
    # Parse invite link
    if not invite_link.startswith("message-via-tor://invite/"):
        return {
            "return": "Error: Invalid invite link format",
            "error": "Invalid format"
        }
    
    try:
        # Extract base64 data
        invite_b64 = invite_link.replace("message-via-tor://invite/", "")
        invite_json = base64.urlsafe_b64decode(invite_b64).decode()
        invite_data = json.loads(invite_json)
    except Exception as e:
        return {
            "return": f"Error: Failed to parse invite link - {str(e)}",
            "error": "Parse error"
        }
    
    # Extract peer info
    peer_pubkey = invite_data.get("peer")
    peer_name = invite_data.get("name", "Unknown")
    
    if not peer_pubkey:
        return {
            "return": "Error: No peer pubkey in invite",
            "error": "Missing peer"
        }
    
    # Create peer event
    peer_event = {
        "type": "peer",
        "pubkey": peer_pubkey,
        "name": peer_name,
        "joined_via": "invite"
    }
    
    return {
        "return": "Joined network via invite",
        "newEvents": [peer_event],
        "peer": {
            "pubkey": peer_pubkey,
            "name": peer_name
        }
    }