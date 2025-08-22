def execute(input_data, identity, db):
    """
    Sends sync requests from all identities to all their known peers
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'outgoing' not in db['state']:
        db['state']['outgoing'] = []
    
    # Get all identities and peers
    identities = db['state'].get('identities', [])
    peers = db['state'].get('peers', [])
    
    sent_count = 0
    
    # From each identity, send sync request to each peer
    for identity_obj in identities:
        identity_pubkey = identity_obj.get('pubkey')
        if not identity_pubkey:
            continue
            
        for peer in peers:
            peer_pubkey = peer.get('pubkey')
            if not peer_pubkey:
                continue
            
            # Don't send to self
            if identity_pubkey == peer_pubkey:
                continue
            
            # Create sync_peers event
            sync_event = {
                "type": "sync_peers",
                "sender": identity_pubkey
            }
            
            # Create outgoing envelope
            outgoing = {
                "recipient": peer_pubkey,
                "data": sync_event
            }
            
            db['state']['outgoing'].append(outgoing)
            sent_count += 1
    
    return {
        "return": f"Sent sync requests from {len(identities)} identities to {len(peers)} peers",
        "db": db
    }