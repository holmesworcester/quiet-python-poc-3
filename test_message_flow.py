#!/usr/bin/env python3
"""Test message flow to find specific error"""
import os
import sys
from pathlib import Path

# Add the root directory to path for core imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from core.api import execute_api
from core.db import PersistentDatabase

# Enable debug mode
os.environ["TEST_MODE"] = "1"
os.environ["CRYPTO_MODE"] = "dummy"

def test_message_flow():
    # Reset database
    db_path = "test_message_flow.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    print("=== Testing Message Flow ===")
    
    # 1. Create Alice
    print("\n1. Creating Alice...")
    response = execute_api("message_via_tor", "POST", "/identities", {"name": "Alice"})
    print(f"Response status: {response.get('status')}")
    alice_id = response.get('body', {}).get('identityId')
    print(f"Alice ID: {alice_id}")
    
    # 2. Create Bob  
    print("\n2. Creating Bob...")
    response = execute_api("message_via_tor", "POST", "/identities", {"name": "Bob"})
    print(f"Response status: {response.get('status')}")
    bob_id = response.get('body', {}).get('identityId')
    print(f"Bob ID: {bob_id}")
    
    # 3. Check current state
    print("\n3. Checking database state...")
    db = PersistentDatabase(db_path)
    print(f"Identities: {db.get('state', {}).get('identities', [])}")
    print(f"Peers: {db.get('state', {}).get('peers', [])}")
    print(f"Messages: {db.get('state', {}).get('messages', [])}")
    
    # 4. Alice sends message
    print("\n4. Alice sending message...")
    response = execute_api("message_via_tor", "POST", "/messages", {
        "text": "Hello Bob!",
        "senderId": alice_id
    })
    print(f"Response: {response}")
    
    # 5. Check messages after send
    print("\n5. Checking messages after send...")
    db = PersistentDatabase(db_path)
    messages = db.get('state', {}).get('messages', [])
    print(f"Messages in state: {len(messages)}")
    for i, msg in enumerate(messages):
        print(f"  Message {i}: sender={msg.get('sender')}, text={msg.get('text')}, received_by={msg.get('received_by')}")
    
    # 6. Run tick
    print("\n6. Running tick...")
    response = execute_api("message_via_tor", "POST", "/tick", {})
    print(f"Response: {response}")
    
    # 7. Check messages after tick
    print("\n7. Checking messages after tick...")
    db = PersistentDatabase(db_path)
    messages = db.get('state', {}).get('messages', [])
    print(f"Messages in state: {len(messages)}")
    for i, msg in enumerate(messages):
        print(f"  Message {i}: sender={msg.get('sender')}, text={msg.get('text')}, received_by={msg.get('received_by')}")
    
    # 8. Get messages for each identity
    print("\n8. Getting messages via API...")
    for identity_name, identity_id in [("Alice", alice_id), ("Bob", bob_id)]:
        print(f"\nMessages for {identity_name} ({identity_id}):")
        response = execute_api("message_via_tor", "GET", f"/messages/{identity_id}", {})
        print(f"  Status: {response.get('status')}")
        if response.get('status') == 200:
            messages = response.get('body', {}).get('messages', [])
            print(f"  Count: {len(messages)}")
            for msg in messages:
                print(f"    - {msg}")

if __name__ == "__main__":
    test_message_flow()