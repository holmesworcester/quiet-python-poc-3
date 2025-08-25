def execute(input_data, db):
    """
    Sends a sync-request to a recipient peer via outgoing
    """
    recipient = input_data.get("recipient")
    
    if not recipient:
        return {
            "return": "Error: No recipient provided",
            "error": "Missing recipient"
        }
    
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    if 'outgoing' not in db['state']:
        db['state']['outgoing'] = []
    
    # Create sync_peers event
    sync_event = {
        "type": "sync_peers",
        "sender": input_data.get("sender")  # Get sender from input_data
    }
    
    # Create outgoing envelope
    outgoing = {
        "recipient": recipient,
        "data": sync_event
    }
    
    db['state']['outgoing'].append(outgoing)
    
    return {
        "return": f"Sync request sent to {recipient}",
        "db": db
    }