#!/usr/bin/env python3
"""
Generate test data for real crypto tests - simpler approach
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.crypto import encrypt, hash

# Set crypto mode to real
os.environ["CRYPTO_MODE"] = "real"

# Test case 1: Successfully decrypt two-layer envelope
inner_data = {"type": "message", "text": "Hello", "sender": "alice"}
inner_key = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
outer_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

print("Test case 1: Successfully decrypt two-layer envelope")
print(f"Inner data: {json.dumps(inner_data)}")
print(f"Inner key: {inner_key}")
print(f"Outer key: {outer_key}")

# Encrypt inner data
inner_json = json.dumps(inner_data)
inner_encrypted = encrypt(inner_json, inner_key)
print(f"Inner encrypted (nonce): {inner_encrypted['nonce']}")
print(f"Inner encrypted (ciphertext): {inner_encrypted['ciphertext']}")

# Create partial structure with encrypted inner data
inner_key_hash = hash(inner_key)
partial = {
    "innerHash": inner_key_hash,
    "data": inner_encrypted["ciphertext"]  # Just the ciphertext, nonce will be computed from hash
}
print(f"Partial structure: {json.dumps(partial)}")

# Encrypt outer layer
outer_json = json.dumps(partial)
outer_encrypted = encrypt(outer_json, outer_key)
outer_key_hash = hash(outer_key)

# Create wire format: <key_hash:64><nonce:48><ciphertext>
wire_data = outer_key_hash + outer_encrypted["nonce"] + outer_encrypted["ciphertext"]

print(f"\nGenerated wire data: {wire_data}")
print(f"Length: {len(wire_data)}")
print(f"Outer key hash: {outer_key_hash}")
print(f"Inner key hash: {inner_key_hash}")