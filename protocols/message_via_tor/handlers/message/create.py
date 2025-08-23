from datetime import datetime
from core.crypto import sign, get_keypair
import json
import time


def execute(input_data, identity, db):
    """
    Create a new message event command.
    Creates canonical signed event and puts it in outgoing envelope if recipient specified.
    """
    # Support both "content" and "text" fields for compatibility
    content = input_data.get("content") or input_data.get("text")
    if not content:
        raise ValueError("Message content is required")
    
    # Get keypair for signing
    keypair = get_keypair(identity)
    private_key = keypair["private"]
    public_key = keypair["public"]
    
    # Get current time from input or use current time
    time_now_ms = input_data.get("time_now_ms", int(time.time() * 1000))
    
    # Create canonical event data
    event_data = {
        "type": "message",
        "text": content,
        "sender": public_key,
        "timestamp": time_now_ms
    }
    
    # Add recipient if provided
    recipient = input_data.get("recipient")
    if recipient:
        event_data["recipient"] = recipient
    
    # Add replyTo if provided
    reply_to = input_data.get("replyTo")
    if reply_to:
        event_data["replyTo"] = reply_to
    
    # Sign the canonical event
    data_str = json.dumps(event_data, sort_keys=True)
    signature = sign(data_str, private_key)
    event_data["sig"] = signature
    
    # If recipient specified, create outgoing envelope
    if recipient:
        # Initialize state if needed
        if 'state' not in db:
            db['state'] = {}
        
        if 'outgoing' not in db['state']:
            db['state']['outgoing'] = []
        
        # Create outgoing envelope
        outgoing = {
            "recipient": recipient,
            "data": event_data
        }
        
        db['state']['outgoing'].append(outgoing)
        
        return {
            "return": "Message sent to outgoing",
            "newEvents": [event_data],
            "messageId": f"msg-{time_now_ms}",
            "db": db
        }
    
    # Return the canonical signed event for local handling
    return {
        "return": "Created",
        "newEvents": [event_data],
        "messageId": f"msg-{time_now_ms}"
    }