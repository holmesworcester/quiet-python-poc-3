def execute(input_data, db):
    """
    Given a peer public key, returns all messages known to that peer
    """
    # API passes peerId as path parameter
    peer_pubkey = input_data.get("peerId")
    
    if not peer_pubkey:
        return {
            "api_response": {
                "return": "Error: No peer ID provided",
                "error": "Missing peerId"
            }
        }
    
    # Get messages from state
    messages = db.get('state', {}).get('messages', [])
    
    # Filter messages visible to this peer (received by or sent by)
    # Also exclude messages marked as unknown_peer
    peer_messages = []
    for msg in messages:
        # Skip messages from unknown peers
        if msg.get('unknown_peer'):
            continue
            
        # Only show messages received by this peer
        if msg.get('received_by') == peer_pubkey:
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
        "api_response": {
            "return": f"Found {len(peer_messages)} messages",
            "messages": peer_messages
        }
    }