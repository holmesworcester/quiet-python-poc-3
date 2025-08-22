def execute(input_data, identity, db):
    """
    Converts all outgoing events to recipient peer to incoming events for that recipient
    """
    # Initialize incoming if needed
    if 'incoming' not in db:
        db['incoming'] = []
    
    # Get outgoing messages
    outgoing = db.get('state', {}).get('outgoing', [])
    
    if not outgoing:
        return {
            "return": "No messages to deliver",
            "db": db
        }
    
    # Move all outgoing to incoming
    delivered_count = 0
    for envelope in outgoing:
        # Add to incoming - the recipient info will be used for routing
        db['incoming'].append(envelope)
        delivered_count += 1
    
    # Clear outgoing
    if 'state' in db:
        db['state']['outgoing'] = []
    
    return {
        "return": f"Delivered {delivered_count} messages",
        "db": db
    }