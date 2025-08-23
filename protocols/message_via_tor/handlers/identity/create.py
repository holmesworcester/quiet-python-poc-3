from core.crypto import get_keypair
import json


def execute(input_data, identity, db):
    """
    Creates an identity containing pubkey, privkey, and calls peer.create
    """
    # Generate a new keypair for this identity
    keypair = get_keypair(identity)
    privkey = keypair["private"]
    pubkey = keypair["public"]
    
    # Create identity event
    identity_event = {
        "type": "identity",
        "pubkey": pubkey,
        "privkey": privkey,
        "name": input_data.get("name", identity)
    }
    
    # Also create a peer event for this identity
    peer_event = {
        "type": "peer",
        "pubkey": pubkey,
        "name": input_data.get("name", identity)
    }
    
    return {
        "return": "Identity created",
        "newEvents": [identity_event, peer_event],
        "identity": {
            "pubkey": pubkey,
            "name": input_data.get("name", identity)
        }
    }