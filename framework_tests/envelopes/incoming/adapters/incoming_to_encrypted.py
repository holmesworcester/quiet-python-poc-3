import json

def adapt(envelope, db, identity):
    """Adapter: incoming -> encrypted"""
    if envelope.get("envelope") != "incoming":
        return None
    
    metadata = envelope.get("metadata", {})
    
    # Check if already encrypted
    if metadata.get("encrypted"):
        # Already encrypted, just change envelope type
        return {
            "envelope": "encrypted",
            "data": envelope.get("data"),
            "metadata": metadata
        }
    
    # Not encrypted, this adapter doesn't handle unencrypted incoming
    # (that would go through incoming -> verifiedPlaintext path)
    return None

# Adapter metadata
ADAPTER = {
    "from": "incoming",
    "to": "encrypted",
    "function": adapt
}