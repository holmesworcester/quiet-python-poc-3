def project(db, envelope, time_now_ms):
    """
    Project message events into state.
    Validates (e.g., known sender), updates state.messages if valid.
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    # Get data and metadata
    data = envelope.get('data', {})
    metadata = envelope.get('metadata', {})
    
    # Get sender
    sender = data.get("sender") or metadata.get("sender")
    
    # Store in eventStore as a list
    if 'eventStore' not in db:
        db['eventStore'] = []
    
    db['eventStore'].append(data)
    
    # Check if sender is known
    known_senders = db['state'].get("known_senders", [])
    
    if sender in known_senders:
        # Valid - update state
        if "messages" not in db['state']:
            db['state']["messages"] = []
        
        # Extract message info - preserve all fields from data
        message = data.copy()
        
        # Ensure we have a text field
        if "text" not in message and "content" in message:
            message["text"] = message["content"]
        
        # Add optional fields if present
        if sender:
            message["sender"] = sender
        if metadata.get("verified"):
            message["verified"] = True
        if data.get("event_id"):
            message["id"] = data["event_id"]
        if data.get("timestamp"):
            message["timestamp"] = data["timestamp"]
        
        # Add replyTo if present
        if "replyTo" in data:
            message["replyTo"] = data["replyTo"]
        
        # Add to messages
        db['state']["messages"].append(message)
        
        # Update conversation threads
        if "threads" not in db['state']:
            db['state']["threads"] = {}
        
        # If this is a reply, add to thread
        if "replyTo" in data:
            thread_id = data["replyTo"]
            if thread_id not in db['state']["threads"]:
                db['state']["threads"][thread_id] = []
            db['state']["threads"][thread_id].append(message.get("id", "unknown"))
        
        # Update last activity
        if data.get("timestamp"):
            db['state']["lastActivity"] = data["timestamp"]
    else:
        # Invalid - ensure messages list exists but don't add to it
        if "messages" not in db['state']:
            db['state']["messages"] = []
        
        # Add to pending since sender is unknown
        if "pending" not in db['state']:
            db['state']["pending"] = []
        db['state']["pending"].append({"event": "..."})
    
    return db