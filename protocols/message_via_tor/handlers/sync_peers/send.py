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
    
    # Persist to SQL outgoing if available
    try:
        if hasattr(db, 'conn'):
            import json
            cur = db.conn.cursor()
            cur.execute(
                "INSERT INTO outgoing(recipient, data, created_at, sent) VALUES(?, ?, ?, 0)",
                (recipient, json.dumps(sync_event), int(input_data.get('time_now_ms') or 0))
            )
            db.conn.commit()
    except Exception:
        pass
    
    return {
        "return": f"Sync request sent to {recipient}"
    }
