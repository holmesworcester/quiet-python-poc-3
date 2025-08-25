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
    
    # Get eventStore, modify it, and reassign to trigger persistence
    event_store = db['eventStore']
    event_store.append(data)
    db['eventStore'] = event_store  # Trigger persistence!
    
    # Check if sender is known
    known_senders = db['state'].get("known_senders", [])
    
    if sender in known_senders:
        # Valid - update state
        state = db['state']
        if "messages" not in state:
            state["messages"] = []
        
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
        state["messages"].append(message)
        
        # Update conversation threads
        if "threads" not in state:
            state["threads"] = {}
        
        # If this is a reply, add to thread
        if "replyTo" in data:
            thread_id = data["replyTo"]
            if thread_id not in state["threads"]:
                state["threads"][thread_id] = []
            state["threads"][thread_id].append(message.get("id", "unknown"))
        
        # Update last activity
        if data.get("timestamp"):
            state["lastActivity"] = data["timestamp"]
        
        db['state'] = state  # Trigger persistence!
    else:
        # Invalid - ensure messages list exists but don't add to it
        state = db['state']
        if "messages" not in state:
            state["messages"] = []
        
        # Add to pending since sender is unknown
        if "pending" not in state:
            state["pending"] = []
        state["pending"].append({"event": "..."})
        
        db['state'] = state  # Trigger persistence!
    
    return db