def execute(input_data, identity, db):
    """
    Given a peer public key, returns all messages known to that peer
    """
    peer_pubkey = input_data.get("peer_pubkey")
    
    if not peer_pubkey:
        return {
            "return": "Error: No peer pubkey provided",
            "error": "Missing peer_pubkey"
        }
    
    # Get messages from state
    messages = db.get('state', {}).get('messages', [])
    
    # Filter messages for this peer (sent by or to this peer)
    peer_messages = []
    for msg in messages:
        if msg.get('sender') == peer_pubkey or msg.get('recipient') == peer_pubkey:
            peer_messages.append({
                "text": msg.get('text'),
                "sender": msg.get('sender'),
                "recipient": msg.get('recipient'),
                "timestamp": msg.get('timestamp'),
                "id": msg.get('id')
            })
    
    # Sort by timestamp
    peer_messages.sort(key=lambda m: m.get('timestamp', 0))
    
    return {
        "return": f"Found {len(peer_messages)} messages",
        "messages": peer_messages
    }