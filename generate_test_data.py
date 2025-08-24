#!/usr/bin/env python3
"""
Generate properly encrypted test data for the real crypto tests.
"""
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocols.framework_tests.handlers.incoming.process_incoming import create_encrypted_blob

# Test case 1: Successfully decrypt two-layer envelope
inner_data = {"type": "message", "text": "Hello", "sender": "alice"}
inner_key = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
outer_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

print("Test case 1: Successfully decrypt two-layer envelope")
print(f"Inner data: {json.dumps(inner_data)}")
print(f"Inner key: {inner_key}")
print(f"Outer key: {outer_key}")

# Set crypto mode to real
os.environ["CRYPTO_MODE"] = "real"

# Generate encrypted blob
wire_data = create_encrypted_blob(inner_data, inner_key, outer_key)
print(f"Generated wire data: {wire_data}")
print(f"Outer key hash (first 64 chars): {wire_data[:64]}")
print()

# Test case 2: Missing inner key
# For this we need to generate data with a different inner key
inner_data_2 = {"type": "message", "text": "Inner key test", "sender": "bob"} 
unknown_inner_key = "1111111111111111111111111111111111111111111111111111111111111111"
outer_key_2 = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

print("Test case 2: Missing inner key") 
print(f"Inner data: {json.dumps(inner_data_2)}")
print(f"Inner key (unknown): {unknown_inner_key}")
print(f"Outer key: {outer_key_2}")

wire_data_2 = create_encrypted_blob(inner_data_2, unknown_inner_key, outer_key_2)
print(f"Generated wire data: {wire_data_2}")
print(f"Outer key hash (first 64 chars): {wire_data_2[:64]}")
print()

# Also generate the inner key hash for reference
from core.crypto import hash
print(f"Inner key hash for unknown key: {hash(unknown_inner_key)}")