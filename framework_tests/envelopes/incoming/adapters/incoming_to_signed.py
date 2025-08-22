def adapt(envelope, db, identity):
    """Adapter: incoming -> signed (for already signed incoming messages)"""
    if envelope.get("envelope") != "incoming":
        return None
    
    metadata = envelope.get("metadata", {})
    
    # Check if this is a signed message
    if metadata.get("signature") and metadata.get("sender"):
        # Already signed, just change envelope type
        return {
            "envelope": "signed",
            "data": envelope.get("data"),
            "metadata": metadata
        }
    
    # Not signed, this adapter doesn't handle unsigned incoming
    return None

# Adapter metadata
ADAPTER = {
    "from": "incoming",
    "to": "signed",
    "function": adapt
}