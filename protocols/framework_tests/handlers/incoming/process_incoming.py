import json
import os
from core.crypto import decrypt, hash, get_crypto_mode, encrypt
from core.handle import handle


def execute(input_data, db):
    """
    Process incoming message queue by decrypting and routing to handlers.
    This replaces the greedy_decrypt functionality as a handler job.
    """
    # Get incoming blobs
    incoming_blobs = db.get('incoming', [])[:]
    db['incoming'] = []
    
    # Process each blob
    for i, blob in enumerate(incoming_blobs):
        if os.environ.get("TEST_MODE"):
            print(f"[process_incoming] Processing blob {i+1}/{len(incoming_blobs)}")
        
        envelope = greedy_decrypt_blob(blob, db)
        if envelope is None:
            if os.environ.get("TEST_MODE"):
                print(f"[process_incoming] Blob {i+1} dropped (decryption failed)")
            continue  # Dropped
        
        if os.environ.get("TEST_MODE"):
            print(f"[process_incoming] Blob {i+1} decrypted successfully, handling envelope")
        
        # Handle the envelope
        db = handle(db, envelope, input_data.get("time_now_ms"))
    
    return {"db": db}


def greedy_decrypt_blob(raw_blob, db):
    """
    Attempt to decrypt an incoming blob through two layers.
    Wire format: <key_hash:64><nonce:48><ciphertext:remaining>
    """
    if os.environ.get("TEST_MODE"):
        print(f"[greedy_decrypt] CRYPTO_MODE={get_crypto_mode()}")
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
        if os.environ.get("TEST_MODE"):
            print(f"[greedy_decrypt] Missing outer key: {outer_hash}")
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
            if os.environ.get("TEST_MODE"):
                print(f"[greedy_decrypt] Attempting outer decrypt with:")
                print(f"  - Cipher length: {len(outer_cipher)}")
                print(f"  - Nonce: {outer_nonce}")
                print(f"  - Key: {outer_key}")
            decrypted_outer = decrypt(outer_cipher, outer_nonce, outer_key)
            if isinstance(decrypted_outer, bytes):
                decrypted_outer = decrypted_outer.decode('utf-8')
        except Exception as e:
            if os.environ.get("TEST_MODE"):
                print(f"[greedy_decrypt] Outer decryption failed: {e}")
            return None  # Drop - decryption failed
        
    envelope["metadata"]["outerKeyHash"] = outer_hash
    
    try:
        if isinstance(decrypted_outer, str):
            partial = json.loads(decrypted_outer)
        elif isinstance(decrypted_outer, bytes):
            partial = json.loads(decrypted_outer.decode())
        else:
            return None  # Drop - invalid data type
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
        if os.environ.get("TEST_MODE"):
            print(f"[greedy_decrypt] Failed to parse outer JSON: {e}")
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
        # Real mode: inner data has format <nonce:48><ciphertext>
        if len(inner_data) < 48:
            if os.environ.get("TEST_MODE"):
                print(f"[greedy_decrypt] Inner data too short for real crypto format")
            return None  # Drop - invalid format
        
        inner_nonce = inner_data[:48]
        inner_ciphertext = inner_data[48:]
        
        try:
            if os.environ.get("TEST_MODE"):
                print(f"[greedy_decrypt] Attempting inner decrypt with:")
                print(f"  - Cipher length: {len(inner_ciphertext)}")
                print(f"  - Nonce: {inner_nonce}")
                print(f"  - Key: {inner_key}")
            decrypted_inner = decrypt(inner_ciphertext, inner_nonce, inner_key)
            if isinstance(decrypted_inner, bytes):
                decrypted_inner = decrypted_inner.decode('utf-8')
        except Exception as e:
            if os.environ.get("TEST_MODE"):
                print(f"[greedy_decrypt] Inner decryption failed: {e}")
            return None  # Drop - decryption failed
        
    envelope["metadata"]["innerKeyHash"] = inner_hash
    
    try:
        if isinstance(decrypted_inner, str):
            envelope["data"] = json.loads(decrypted_inner)
        elif isinstance(decrypted_inner, bytes):
            envelope["data"] = json.loads(decrypted_inner.decode())
        else:
            return None  # Drop - invalid data type
        # Hash the canonical event for event_id
        envelope["metadata"]["eventId"] = hash(json.dumps(envelope["data"], sort_keys=True))
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return None  # Drop - invalid JSON
    
    return envelope


def create_encrypted_blob(inner_data, inner_key, outer_key):
    """
    Helper to create properly encrypted test data.
    Returns the wire format blob.
    """
    from core.crypto import encrypt, hash, get_crypto_mode
    
    # Serialize inner data
    inner_json = json.dumps(inner_data)
    
    if get_crypto_mode() == "dummy":
        # In dummy mode, inner data is just the JSON string
        inner_encrypted_data = inner_json
    else:
        # In real mode, properly encrypt the inner data
        # We need to store both nonce and ciphertext for the inner layer
        inner_encrypted = encrypt(inner_json, inner_key)
        # Create wire format for inner layer: <nonce:48><ciphertext>
        inner_encrypted_data = inner_encrypted["nonce"] + inner_encrypted["ciphertext"]
    
    # Create partial with encrypted inner data
    inner_key_hash = hash(inner_key)
    partial = {
        "innerHash": inner_key_hash,
        "data": inner_encrypted_data
    }
    
    # Encrypt outer layer
    outer_json = json.dumps(partial)
    outer_encrypted = encrypt(outer_json, outer_key)
    outer_key_hash = hash(outer_key)
    
    # Create wire format: <key_hash:64><nonce:48><ciphertext>
    wire_data = outer_key_hash + outer_encrypted["nonce"] + outer_encrypted["ciphertext"]
    
    return wire_data