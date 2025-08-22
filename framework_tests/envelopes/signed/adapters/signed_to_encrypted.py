import json
from core.crypto import encrypt, hash

def adapt(envelope, db, identity):
    """Adapter: signed -> encrypted"""
    if envelope.get("envelope") != "signed":
        return None
    
    # Serialize the entire signed envelope for encryption
    plaintext = json.dumps(envelope, sort_keys=True)
    
    # Generate encryption key (in real system, would use recipient's key)
    encryption_key = hash(f"{identity}_encryption_key")[:64]  # 32 bytes hex
    
    # Encrypt the envelope
    encrypted_result = encrypt(plaintext, encryption_key)
    
    # Create encrypted envelope
    result = {
        "envelope": "encrypted",
        "data": encrypted_result["ciphertext"],
        "metadata": {
            "encrypted": True,
            "algorithm": encrypted_result["algorithm"],
            "nonce": encrypted_result["nonce"]
        }
    }
    
    # Copy some metadata from signed envelope
    if "sender" in envelope.get("metadata", {}):
        result["metadata"]["sender"] = envelope["metadata"]["sender"]
    
    # Add event_id as hash of encrypted envelope
    canonical = json.dumps(result, sort_keys=True)
    event_id = hash(canonical)[:16]
    result["metadata"]["event_id"] = event_id
    
    return result

# Adapter metadata
ADAPTER = {
    "from": "signed",
    "to": "encrypted",
    "function": adapt
}