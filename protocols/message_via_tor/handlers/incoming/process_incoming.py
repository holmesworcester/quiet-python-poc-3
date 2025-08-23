from core.handle import handle


def execute(input_data, identity, db):
    """
    Process incoming message queue for message_via_tor protocol.
    This protocol doesn't use message layer encryption, so we just
    pass through the messages as envelopes.
    """
    # Get incoming blobs
    incoming_blobs = db.get('incoming', [])[:]
    db['incoming'] = []
    
    # Process each blob
    for blob in incoming_blobs:
        # For message_via_tor, incoming blobs are already in envelope format
        # Just ensure they have the proper structure
        envelope = ensure_envelope_format(blob)
        
        # Handle the envelope
        db = handle(db, envelope, input_data.get("time_now_ms"), identity)
    
    return {"db": db}


def ensure_envelope_format(blob):
    """
    Ensure the blob is in proper envelope format.
    For message_via_tor, we expect blobs to already contain the event data.
    """
    # If it's already an envelope, return as-is
    if "data" in blob and "metadata" in blob:
        return blob
    
    # Otherwise, wrap it in envelope format
    return {
        "data": blob,
        "metadata": {
            "origin": blob.get("origin"),
            "receivedAt": blob.get("received_at"),
            "selfGenerated": False
        }
    }