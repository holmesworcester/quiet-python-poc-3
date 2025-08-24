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
    
    # Process each envelope
    for envelope in incoming_blobs:
        # tor_simulator always provides proper envelopes
        # Handle the envelope with the recipient from the envelope
        db = handle(db, envelope, input_data.get("time_now_ms"), envelope.get("recipient"))
    
    return {"db": db}