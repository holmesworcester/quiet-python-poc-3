def execute(input_data, db):
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
    current_time_ms = input_data.get('time_now_ms', 0)
    
    for envelope in outgoing:
        # Wrap as pre-decrypted envelope for incoming handler
        recipient = envelope.get("recipient")
        incoming_envelope = {
            "recipient": recipient,
            "envelope": True,
            "data": envelope.get("data"),
            "metadata": {
                "origin": "network",
                "receivedAt": current_time_ms,
                "selfGenerated": False,
                "received_by": recipient  # Add who received this message
            }
        }
        db['incoming'].append(incoming_envelope)
        delivered_count += 1
    
    # Clear outgoing
    if 'state' in db:
        db['state']['outgoing'] = []
    
    return {
        "return": f"Delivered {delivered_count} messages",
        "db": db
    }