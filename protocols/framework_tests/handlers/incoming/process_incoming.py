import json
from core.crypto import decrypt, hash, get_crypto_mode, encrypt
from core.handle import handle


def execute(input_data, identity, db):
    """
    Process incoming message queue by decrypting and routing to handlers.
    This replaces the greedy_decrypt functionality as a handler job.
    """
    # Get incoming blobs
    incoming_blobs = db.get('incoming', [])[:]
    db['incoming'] = []
    
    # Process each blob
    for blob in incoming_blobs:
        envelope = greedy_decrypt_blob(blob, db)
        if envelope is None:
            continue  # Dropped
        
        # Handle the envelope
        db = handle(db, envelope, input_data.get("time_now_ms"), identity)
    
    return {"db": db}


def greedy_decrypt_blob(raw_blob, db):
    """
    Attempt to decrypt an incoming blob through two layers.
    Wire format: <key_hash:64><nonce:48><ciphertext:remaining>
    """
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
    if "data" not in raw_blob:
        return None
    
    raw_data = raw_blob["data"]
    
    # Parse wire format based on crypto mode
    if get_crypto_mode() == "dummy":
        # Dummy mode: <key_hash:64><ciphertext:remaining>
        if len(raw_data) < 64:
            return None
        outer_hash = raw_data[:64]
        outer_cipher = raw_data[64:]
        outer_nonce = None
    else:
        # Real mode: <key_hash:64><nonce:48><ciphertext:remaining>
        if len(raw_data) < 112:  # 64 + 48
            return None
        outer_hash = raw_data[:64]
        outer_nonce = raw_data[64:112]
        outer_cipher = raw_data[112:]
    
    outer_key = db.get("state", {}).get("key_map", {}).get(outer_hash)
    
    if not outer_key:
        envelope["metadata"]["error"] = f"Missing outer key: {outer_hash}"
        envelope["metadata"]["inNetwork"] = False
        envelope["metadata"]["missingHash"] = outer_hash
        return envelope
    
    # Decrypt outer layer
    if get_crypto_mode() == "dummy":
        decrypted_outer = outer_cipher
    else:
        # Real crypto with nonce
        try:
            decrypted_outer = decrypt(outer_cipher, outer_nonce, outer_key)
            if isinstance(decrypted_outer, bytes):
                decrypted_outer = decrypted_outer.decode('utf-8')
        except Exception:
            return None  # Drop - decryption failed
        
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
    
    inner_data = partial.get("data")
    if not inner_data:
        return None  # Drop - no data field
    
    # Parse inner layer based on crypto mode
    if get_crypto_mode() == "dummy":
        decrypted_inner = inner_data
    else:
        # Use hash of the encrypted inner data as nonce
        inner_nonce_full = hash(inner_data)
        # NaCl expects 24-byte nonce, so take first 24 bytes of hash
        inner_nonce = inner_nonce_full[:48]  # 48 hex chars = 24 bytes
        
        try:
            decrypted_inner = decrypt(inner_data, inner_nonce, inner_key)
            if isinstance(decrypted_inner, bytes):
                decrypted_inner = decrypted_inner.decode('utf-8')
        except Exception:
            return None  # Drop - decryption failed
        
    envelope["metadata"]["innerKeyHash"] = inner_hash
    
    try:
        envelope["data"] = json.loads(decrypted_inner) if isinstance(decrypted_inner, str) else json.loads(decrypted_inner.decode())
        # Hash the canonical event for event_id
        envelope["metadata"]["eventId"] = hash(json.dumps(envelope["data"], sort_keys=True))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None  # Drop - invalid JSON
    
    return envelope


def create_encrypted_blob(inner_data, inner_key, outer_key):
    """
    Helper to create properly encrypted test data.
    Returns the wire format blob.
    """
    from core.crypto import encrypt, hash
    
    # Serialize inner data
    inner_json = json.dumps(inner_data)
    
    # First encrypt to get initial ciphertext for hash-based nonce
    inner_encrypted = encrypt(inner_json, inner_key)
    
    # Use hash of ciphertext as nonce for deterministic encryption
    inner_nonce_full = hash(inner_encrypted["ciphertext"])
    inner_nonce = inner_nonce_full[:48]  # 48 hex chars = 24 bytes
    
    # Re-encrypt with the deterministic nonce
    box = __import__('nacl.secret', fromlist=['SecretBox']).SecretBox(
        __import__('nacl.encoding', fromlist=['HexEncoder']).HexEncoder.decode(inner_key)
    )
    inner_ciphertext_bytes = __import__('nacl.encoding', fromlist=['HexEncoder']).HexEncoder.decode(inner_encrypted["ciphertext"])
    inner_nonce_bytes = __import__('nacl.encoding', fromlist=['HexEncoder']).HexEncoder.decode(inner_nonce)
    
    # Encrypt with specific nonce
    encrypted_msg = box.encrypt(inner_json.encode(), inner_nonce_bytes)
    final_inner_ciphertext = __import__('nacl.encoding', fromlist=['HexEncoder']).HexEncoder.encode(encrypted_msg.ciphertext).decode()
    
    # Create partial with encrypted inner data
    inner_key_hash = hash(inner_key)
    partial = {
        "innerHash": inner_key_hash,
        "data": final_inner_ciphertext
    }
    
    # Encrypt outer layer
    outer_json = json.dumps(partial)
    outer_encrypted = encrypt(outer_json, outer_key)
    outer_key_hash = hash(outer_key)
    
    # Create wire format: <key_hash:64><nonce:48><ciphertext>
    wire_data = outer_key_hash + outer_encrypted["nonce"] + outer_encrypted["ciphertext"]
    
    return wire_data