import json
from core.crypto import verify

def adapt(envelope, db, identity):
    """Adapter: signed -> verifiedPlaintext"""
    if envelope.get("envelope") != "signed":
        return None
    
    metadata = envelope.get("metadata", {})
    signature = metadata.get("signature")
    sender = metadata.get("sender")
    
    # The sender IS the public key in our system
    public_key = metadata.get("publicKey", sender)
    
    if not all([signature, sender]):
        return None
    
    # Create canonical representation to verify
    # In our system, we sign just the data
    canonical = json.dumps(envelope.get("data", {}), sort_keys=True)
    
    # For dummy mode, we don't need the public key
    if signature.startswith("dummy_sig_"):
        public_key = public_key or "dummy_key"
    
    if not public_key:
        return None
    
    # Verify signature
    if verify(canonical, signature, public_key):
        return {
            "envelope": "verifiedPlaintext",
            "data": envelope.get("data", {}),
            "metadata": {
                **metadata,
                "verified": True
            }
        }
    
    # Signature verification failed
    return None

# Adapter metadata
ADAPTER = {
    "from": "signed",
    "to": "verifiedPlaintext",
    "function": adapt
}