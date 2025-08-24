from core.crypto import sign, get_keypair
import json
import time


def execute(input_data, identity, db):
    """
    Create a new message event command.
    Creates canonical signed event and broadcasts it to all known peers of the identity.
    """
    # Get message text
    text = input_data.get("text")
    if not text:
        raise ValueError("Message text is required")
    
    # Get keypair for signing
    # First check if we have this identity stored (identity might be a pubkey)
    identities = db.get('state', {}).get('identities', [])
    stored_identity = None
    
    # Handle both list and dict formats
    if isinstance(identities, list):
        for id_data in identities:
            if id_data.get('pubkey') == identity:
                stored_identity = id_data
                break
    elif isinstance(identities, dict) and identity in identities:
        # Old test format: identities as dict with identity name as key
        id_data = identities[identity]
        if 'keypair' in id_data:
            stored_identity = {
                'pubkey': id_data['keypair']['public'],
                'privkey': id_data['keypair']['private']
            }
    
    if stored_identity:
        # Use the stored keys directly
        private_key = stored_identity['privkey']
        public_key = stored_identity['pubkey']
    else:
        # Generate keypair (for backward compatibility with tests)
        keypair = get_keypair(identity)
        private_key = keypair["private"]
        public_key = keypair["public"]
    
    # Get current time from input or use current time
    time_now_ms = input_data.get("time_now_ms", int(time.time() * 1000))
    
    # Create canonical event data
    event_data = {
        "type": "message",
        "text": text,
        "sender": public_key,
        "timestamp": time_now_ms
    }
    
    # Sign the canonical event
    data_str = json.dumps(event_data, sort_keys=True)
    signature = sign(data_str, private_key)
    event_data["sig"] = signature
    
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'outgoing' not in db['state']:
        db['state']['outgoing'] = []
    
    # Get all peers known by this identity
    peers = db['state'].get('peers', [])
    known_peers = [p for p in peers if p.get('received_by') == public_key]
    
    
    # Create outgoing envelope for each known peer
    sent_count = 0
    for peer in known_peers:
        peer_pubkey = peer.get('pubkey')
        if not peer_pubkey:
            continue
        
        # Don't send to self
        if public_key == peer_pubkey:
            continue
        
        # Create outgoing envelope
        outgoing = {
            "recipient": peer_pubkey,
            "data": event_data
        }
        
        db['state']['outgoing'].append(outgoing)
        sent_count += 1
    
    return {
        "api_response": {
            "return": f"Message broadcast to {sent_count} peers",
            "messageId": f"msg-{time_now_ms}",
            "sentTo": sent_count
        },
        "newEvents": [event_data],
        "db": db
    }