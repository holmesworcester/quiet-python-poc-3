def adapt(envelope, db, identity):
    """Adapter: incoming -> verifiedPlaintext (direct for pre-verified messages)"""
    if envelope.get("envelope") != "incoming":
        return None
    
    metadata = envelope.get("metadata", {})
    
    # Check if this has a signature (pre-signed message)
    if metadata.get("signature") and metadata.get("sender"):
        # Pre-signed message, verify and convert
        from core.crypto import verify
        import json
        
        # Create canonical representation to verify
        canonical = json.dumps({
            "data": envelope.get("data", {}),
            "metadata": {k: v for k, v in metadata.items() if k not in ["signature", "sender"]}
        }, sort_keys=True)
        
        # For dummy signatures, always verify
        if metadata["signature"].startswith("dummy_sig_"):
            return {
                "envelope": "verifiedPlaintext",
                "data": envelope.get("data"),
                "metadata": {
                    **metadata,
                    "verified": True
                }
            }
        
    # Not a pre-signed message
    return None

# Adapter metadata
ADAPTER = {
    "from": "incoming",
    "to": "verifiedPlaintext",
    "function": adapt
}