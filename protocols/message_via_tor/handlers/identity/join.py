import json
import base64
import os
import sys

# Add handler path to sys.path for imports
handler_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if handler_dir not in sys.path:
    sys.path.insert(0, handler_dir)

from identity import create as identity_create


def execute(input_data, identity, db):
    """
    Consumes a valid invite link, creates an identity for the joining user
    and a peer event for the peer in invite
    """
    # Get the name for the new identity
    name = input_data.get("name")
    if not name:
        return {
            "api_response": {
                "error": "Name is required when joining"
            }
        }
    
    # Check both camelCase and snake_case for compatibility
    invite_link = input_data.get("inviteLink") or input_data.get("invite_link", "")
    
    # Parse invite link
    if not invite_link.startswith("message-via-tor://invite/"):
        return {
            "api_response": {
                "error": "Invalid invite link format"
            }
        }
    
    try:
        # Extract base64 data
        invite_b64 = invite_link.replace("message-via-tor://invite/", "")
        invite_json = base64.urlsafe_b64decode(invite_b64).decode()
        invite_data = json.loads(invite_json)
    except Exception as e:
        return {
            "api_response": {
                "error": f"Failed to parse invite link - {str(e)}"
            }
        }
    
    # Extract peer info
    peer_pubkey = invite_data.get("peer")
    peer_name = invite_data.get("name", "Unknown")
    
    if not peer_pubkey:
        return {
            "api_response": {
                "error": "No peer pubkey in invite"
            }
        }
    
    # Use identity.create to create the new identity (DRY principle)
    create_result = identity_create.execute({"name": name}, identity, db)
    
    # Extract the created identity info
    new_pubkey = create_result["api_response"]["identity"]["pubkey"]
    
    # Get the events created by identity.create
    identity_events = create_result.get("newEvents", [])
    
    # Create peer event for the inviter
    inviter_peer_event = {
        "type": "peer",
        "pubkey": peer_pubkey,
        "name": peer_name,
        "joined_via": "invite",
        "received_by": new_pubkey  # This peer is known by the new identity
    }
    
    # Combine all events
    all_events = identity_events + [inviter_peer_event]
    
    return {
        "api_response": {
            "return": "Joined network via invite",
            "identity": {
                "pubkey": new_pubkey,
                "name": name
            },
            "peer": {
                "pubkey": peer_pubkey,
                "name": peer_name
            }
        },
        "newEvents": all_events
    }