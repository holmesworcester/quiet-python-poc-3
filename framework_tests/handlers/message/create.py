from datetime import datetime

def execute(input_data, identity, db):
    """
    Create a new message event command.
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
            "timestamp": datetime.utcnow().isoformat() + "Z"
        },
        "metadata": {}
    }
    
    # Add replyTo if provided
    reply_to = input_data.get("replyTo")
    if reply_to:
        envelope["data"]["replyTo"] = reply_to
    
    # If encrypt flag is set, return instruction to encrypt
    encrypt = input_data.get("encrypt", False)
    if encrypt:
        # Sign and encrypt the envelope
        from core.adapter_graph import adapt_envelope
        signed = adapt_envelope(envelope, "signed", db, identity)
        encrypted = adapt_envelope(signed, "encrypted", db, identity)
        envelope = encrypted
    
    return {
        "newlyCreatedEvents": [envelope],
        "new_events": [{"type": "message", "text": content}],  # For test compatibility
        "return": "Created",
        "messageId": f"msg-{datetime.utcnow().timestamp()}"
    }