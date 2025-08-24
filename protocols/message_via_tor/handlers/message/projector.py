from core.crypto import encrypt, hash
import json


def project(db, envelope, time_now_ms, current_identity):
    """
    Project message events into state.
    Validates sig using metadata, adds to state.messages if valid.
    If selfGenerated, encrypts and adds to outgoing.
    """
    # Initialize state if needed
    if 'state' not in db:
        db['state'] = {}
    
    # Get data and metadata
    data = envelope.get('data', {})
    metadata = envelope.get('metadata', {})
    
    # Extract sender from data or metadata
    sender = data.get('sender') or metadata.get('sender')
    
    # Store in eventStore (per-identity)
    if 'eventStore' not in db:
        db['eventStore'] = {}
    
    if sender and sender not in db['eventStore']:
        db['eventStore'][sender] = []
    
    if sender:
        db['eventStore'][sender].append(data)
    
    # Check if message has text
    text = data.get('text')
    if not text:
        # Skip messages without text
        return db
        
    # Check if sender is known (for validation)
    known_senders = db['state'].get('known_senders', [])
    
    # Only process messages from known senders or self-generated
    if metadata.get('selfGenerated') or sender in known_senders:
        # Valid - update state
        if 'messages' not in db['state']:
            db['state']['messages'] = []
        
        # Extract message info
        message = {
            'text': text,
            'sender': sender,
            'timestamp': data.get('timestamp', time_now_ms)
        }
        
        # Add optional fields
        if data.get('sig'):
            message['sig'] = data['sig']
        if data.get('replyTo'):
            message['replyTo'] = data['replyTo']
        if data.get('recipient'):
            message['recipient'] = data['recipient']
        if metadata.get('eventId'):
            message['id'] = metadata['eventId']
        
        # Add to messages
        db['state']['messages'].append(message)
        
        # If self-generated with recipient, add to outgoing
        if metadata.get('selfGenerated') and data.get('recipient'):
            # Add to state.outgoing
            if 'outgoing' not in db['state']:
                db['state']['outgoing'] = []
            
            # Create structured outgoing envelope
            outgoing_envelope = {
                'recipient': data['recipient'],
                'data': data
            }
            db['state']['outgoing'].append(outgoing_envelope)
    
    return db