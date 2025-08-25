#!/usr/bin/env python3
"""Test the demo flow programmatically to find the error"""
import os
import sys
from pathlib import Path

# Add the root directory to path for core imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Change to project root directory for API calls
os.chdir(project_root)

from core.api import execute_api

def test_flow():
    # Reset the database
    import core.db as db_module
    if hasattr(db_module, 'reset_db'):
        db_module.reset_db('demo.db')
    
    print("1. Creating Alice identity...")
    try:
        response = execute_api(
            "message_via_tor",
            "POST",
            "/identities",
            data={"name": "Alice"}
        )
        print(f"   Response: {response}")
        alice_id = response.get('body', {}).get('identityId')
        print(f"   Alice ID: {alice_id}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n2. Creating invite from Alice...")
    try:
        response = execute_api(
            "message_via_tor",
            "POST",
            f"/identities/{alice_id}/invite",
            data={}
        )
        print(f"   Response: {response}")
        invite_link = response.get('body', {}).get('inviteLink')
        print(f"   Invite link: {invite_link}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n3. Bob joining with invite...")
    try:
        response = execute_api(
            "message_via_tor",
            "POST",
            "/join",
            data={
                "name": "Bob",
                "inviteLink": invite_link
            }
        )
        print(f"   Response: {response}")
        bob_id = response.get('body', {}).get('identity', {}).get('pubkey')
        print(f"   Bob ID: {bob_id}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n4. Alice sending message...")
    try:
        response = execute_api(
            "message_via_tor",
            "POST",
            f"/identities/{alice_id}/messages",
            data={"text": "Hello Bob!"}
        )
        print(f"   Response: {response}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n5. Running tick...")
    try:
        response = execute_api(
            "message_via_tor",
            "POST",
            "/tick",
            data={}
        )
        print(f"   Response: {response}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n6. Checking messages for Bob...")
    try:
        response = execute_api(
            "message_via_tor",
            "GET",
            f"/identities/{bob_id}/messages",
            data={}
        )
        print(f"   Response: {response}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_flow()