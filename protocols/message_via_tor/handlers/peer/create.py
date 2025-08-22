def execute(input_data, identity, db):
    """
    Creates and returns a new peer event
    """
    pubkey = input_data.get("pubkey")
    name = input_data.get("name", pubkey[:8] if pubkey else "Unknown")
    
    if not pubkey:
        return {
            "return": "Error: No pubkey provided",
            "error": "Missing pubkey"
        }
    
    # Create peer event
    peer_event = {
        "type": "peer",
        "pubkey": pubkey,
        "name": name
    }
    
    return {
        "return": "Peer created",
        "newEvents": [peer_event],
        "peer": {
            "pubkey": pubkey,
            "name": name
        }
    }