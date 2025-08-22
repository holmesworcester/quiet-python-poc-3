from datetime import datetime
from core.crypto import hash

def adapt(envelope, db, identity):
    """Adapter: encrypted -> outgoing"""
    if envelope.get("envelope") != "encrypted":
        return None
    
    # Transform to outgoing envelope
    metadata = envelope.get("metadata", {}).copy()
    
    # Add timestamp if not present
    if "timestamp" not in metadata:
        metadata["timestamp"] = datetime.utcnow().isoformat() + "Z"
    
    # Add keyId if not present (hash of encryption key)
    if "keyId" not in metadata:
        # In a real system, this would be the recipient's key ID
        # For now, use a hash of the identity as a placeholder
        metadata["keyId"] = hash(f"{identity}_encryption_key")[:16]
    
    # Transform to outgoing
    return {
        "envelope": "outgoing",
        "data": envelope["data"],  # Raw ciphertext string
        "metadata": metadata
    }

# Adapter metadata
ADAPTER = {
    "from": "encrypted",
    "to": "outgoing",
    "function": adapt
}