from core.handle import handle
import uuid
import time


def execute(input_data, db):
    """
    Process incoming message queue for message_via_tor protocol.
    This protocol doesn't use message layer encryption, so we just
    pass through the messages as envelopes.
    """
    # Get incoming blobs
    incoming_blobs = db.get('incoming', [])[:]
    db['incoming'] = []
    
    current_time = input_data.get("time_now_ms", int(time.time() * 1000))
    
    # Process each envelope
    for envelope in incoming_blobs:
        # tor_simulator always provides proper envelopes
        # Add event ID if not present (for incoming network events)
        if 'metadata' in envelope and 'eventId' not in envelope.get('metadata', {}):
            envelope['metadata']['eventId'] = str(uuid.uuid4())
            envelope['metadata']['timestamp'] = envelope['metadata'].get('timestamp', current_time)
        
        # Handle the envelope (auto_transaction=False since we're already in a command transaction)
        db = handle(db, envelope, input_data.get("time_now_ms"), auto_transaction=False)
    
    return {"db": db}