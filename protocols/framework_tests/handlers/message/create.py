from datetime import datetime

def execute(input_data, identity, db):
    """
    Create a new message event command (simplified version).
    Returns newlyCreatedEvents and any other return values.
    """
    # Support both "content" and "text" fields for compatibility
    content = input_data.get("content") or input_data.get("text")
    if not content:
        raise ValueError("Message content is required")
    
    # Create plaintext envelope
    envelope = {
        "envelope": "plaintext",
        "data": {
            "type": "message",
            "content": content,
            "text": content,  # Include both for compatibility
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "metadata": {
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }
    
    # Add replyTo if provided
    reply_to = input_data.get("replyTo")
    if reply_to:
        envelope["data"]["replyTo"] = reply_to
    
    return {
        "newlyCreatedEvents": [envelope],
        "new_events": [{"type": "message", "text": content}],  # For test compatibility
        "return": "Created",
        "messageId": f"msg-{datetime.utcnow().timestamp()}"
    }