import json
from core.crypto import decrypt, hash

def adapt(envelope, db, identity):
    """Adapter: encrypted -> signed"""
    if envelope.get("envelope") != "encrypted":
        return None
    
    metadata = envelope.get("metadata", {})
    ciphertext = envelope.get("data")
    nonce = metadata.get("nonce")
    
    if not ciphertext or not nonce:
        return None
    
    # Generate decryption key (same as encryption key)
    decryption_key = hash(f"{identity}_encryption_key")[:64]  # 32 bytes hex
    
    # Decrypt the envelope
    decrypted_bytes = decrypt(ciphertext, nonce, decryption_key)
    if not decrypted_bytes:
        return None
    
    # Parse the decrypted signed envelope
    try:
        signed = json.loads(decrypted_bytes.decode())
        
        # Preserve event_id if present
        if "event_id" in metadata:
            if "metadata" not in signed:
                signed["metadata"] = {}
            signed["metadata"]["event_id"] = metadata["event_id"]
        
        return signed
    except:
        return None

# Adapter metadata
ADAPTER = {
    "from": "encrypted",
    "to": "signed",
    "function": adapt
}