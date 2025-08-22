def adapt(envelope, db, identity):
    """Adapter: plaintext -> verifiedPlaintext (for trusted local messages)"""
    if envelope.get("envelope") != "plaintext":
        return None
    
    # Extract sender from data or metadata
    data = envelope.get("data", {})
    metadata = envelope.get("metadata", {})
    
    # Look for sender in data first, then metadata, then use identity
    sender = data.get("sender") if isinstance(data, dict) else None
    if not sender:
        sender = metadata.get("sender", identity)
    
    # Convert plaintext directly to verifiedPlaintext (trusted local source)
    return {
        "envelope": "verifiedPlaintext",
        "data": data,
        "metadata": {
            **metadata,
            "sender": sender,
            "verified": True
        }
    }

# Adapter metadata
ADAPTER = {
    "from": "plaintext",
    "to": "verifiedPlaintext",
    "function": adapt
}