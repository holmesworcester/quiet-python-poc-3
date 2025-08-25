def execute(input_data, db):
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
    
    # From each identity, send sync request to peers known by that identity
    for identity_obj in identities:
        identity_pubkey = identity_obj.get('pubkey')
        if not identity_pubkey:
            continue
        
        # Find peers known by this specific identity
        known_peers = [p for p in peers if p.get('received_by') == identity_pubkey]
            
        for peer in known_peers:
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
    
    # Count unique recipients
    unique_recipients = len(set(o['recipient'] for o in db['state']['outgoing'] if o['data'].get('type') == 'sync_peers'))
    
    return {
        "return": f"Sent sync requests from {len(identities)} identities to {unique_recipients} peers",
        "db": db
    }