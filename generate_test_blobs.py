#!/usr/bin/env python3
"""Generate encrypted test blobs for the tests"""
import json
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocols.framework_tests.handlers.incoming.process_incoming import create_encrypted_blob

# Test cases to generate
test_cases = [
    {
        "name": "test_45_real_crypto",
        "env": {"CRYPTO_MODE": "real"},
        "inner_data": {"type": "message", "text": "Hello", "sender": "alice"},
        "inner_key": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
        "outer_key": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    },
    {
        "name": "test_326_unknown_event",
        "env": {"CRYPTO_MODE": "real"},
        "inner_data": {"type": "custom_event_type", "payload": "test data", "sender": "alice"},
        "inner_key": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210", 
        "outer_key": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    },
    {
        "name": "test_364_missing_inner_key",
        "env": {"CRYPTO_MODE": "real"},
        "inner_data": {"type": "message", "text": "Missing inner key test", "sender": "bob"},
        "inner_key": "1111111111111111111111111111111111111111111111111111111111111111",
        "outer_key": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    }
]

# Generate encrypted blobs
for test_case in test_cases:
    # Set environment
    for key, value in test_case["env"].items():
        os.environ[key] = value
    
    # Generate blob
    blob = create_encrypted_blob(
        test_case["inner_data"],
        test_case["inner_key"],
        test_case["outer_key"]
    )
    
    print(f"\n{test_case['name']}:")
    print(f"Generated blob: {blob}")
    print(f"Blob length: {len(blob)}")