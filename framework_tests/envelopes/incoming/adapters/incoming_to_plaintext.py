def adapt(envelope, db, identity):
    """Adapter: incoming -> plaintext (for unencrypted/unsigned messages)"""
    if envelope.get("envelope") != "incoming":
        return None
    
    metadata = envelope.get("metadata", {})
    
    # Check if this is neither encrypted nor signed
    if not metadata.get("encrypted") and not metadata.get("signature"):
        # Plain incoming message, convert to plaintext
        return {
            "envelope": "plaintext",
            "data": envelope.get("data"),
            "metadata": {k: v for k, v in metadata.items() if k != "network_id"}
        }
    
    # This adapter only handles plain incoming
    return None

# Adapter metadata
ADAPTER = {
    "from": "incoming",
    "to": "plaintext",
    "function": adapt
}