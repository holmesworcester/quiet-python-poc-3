import json
from core.crypto import decrypt, hash


def greedy_decrypt(raw_blob, db, current_identity):
    # Check if this is already a decrypted envelope
    if "envelope" in raw_blob and "data" in raw_blob and "metadata" in raw_blob:
        # Already decrypted, return as-is
        return raw_blob
    
    envelope = {
        "data": None,
        "metadata": {
            "origin": raw_blob.get("origin"),
            "receivedAt": raw_blob.get("received_at"),
            "selfGenerated": False
        }
    }
    
    # Outer (transit) layer
    if "data" not in raw_blob or len(raw_blob["data"]) < 64:
        return None
        
    outer_hash = raw_blob["data"][:64]
    outer_key = db.get("state", {}).get("key_map", {}).get(outer_hash)
    
    if not outer_key:
        envelope["metadata"]["error"] = f"Missing outer key: {outer_hash}"
        envelope["metadata"]["inNetwork"] = False
        envelope["metadata"]["missingHash"] = outer_hash
        return envelope
    
    outer_cipher = raw_blob["data"][64:]
    
    # For dummy crypto mode, just treat the cipher as the decrypted data
    from core.crypto import get_crypto_mode
    if get_crypto_mode() == "dummy":
        decrypted_outer = outer_cipher
    else:
        # Real crypto would need nonce - for now, fail
        return None  # Drop - no nonce available in current format
        
    envelope["metadata"]["outerKeyHash"] = outer_hash
    
    try:
        partial = json.loads(decrypted_outer) if isinstance(decrypted_outer, str) else json.loads(decrypted_outer.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None  # Drop - invalid JSON
    
    # Inner layer
    inner_hash = partial.get("innerHash", outer_hash)
    inner_key = db.get("state", {}).get("key_map", {}).get(inner_hash)
    
    if not inner_key:
        envelope["metadata"]["error"] = f"Missing inner key: {inner_hash}"
        envelope["metadata"]["inNetwork"] = True
        envelope["metadata"]["missingHash"] = inner_hash
        envelope["data"] = partial
        return envelope
    
    inner_cipher = partial.get("data")
    if not inner_cipher:
        return None  # Drop - no data field
        
    # For dummy crypto mode, just treat the cipher as the decrypted data  
    if get_crypto_mode() == "dummy":
        decrypted_inner = inner_cipher
    else:
        # Real crypto would need nonce - for now, fail
        return None  # Drop - no nonce available in current format
        
    envelope["metadata"]["innerKeyHash"] = inner_hash
    
    try:
        envelope["data"] = json.loads(decrypted_inner) if isinstance(decrypted_inner, str) else json.loads(decrypted_inner.decode())
        # Hash the canonical event for event_id
        envelope["metadata"]["eventId"] = hash(json.dumps(envelope["data"], sort_keys=True))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None  # Drop - invalid JSON
    
    return envelope