#!/usr/bin/env python3
"""
Update test files to expect full envelopes in eventStore instead of just data.
Since projectors now store the full envelope (with metadata), tests need updating.
"""

import json
import sys
from pathlib import Path

def update_eventstore_in_then(then_obj, given_envelope=None):
    """Update eventStore expectations in 'then' section to use full envelopes"""
    if 'db' not in then_obj:
        return
    
    db = then_obj['db']
    if 'eventStore' not in db:
        return
    
    # Get the current eventStore expectation
    event_store = db['eventStore']
    if not isinstance(event_store, list):
        return
    
    # Update each event to be a full envelope
    updated_events = []
    for event in event_store:
        if isinstance(event, dict) and 'data' not in event:
            # This is raw data, wrap it in an envelope
            envelope = {
                "data": event,
                "metadata": {}
            }
            
            # Try to infer metadata from the given envelope if available
            if given_envelope and 'metadata' in given_envelope:
                envelope['metadata'] = given_envelope['metadata'].copy()
                
            updated_events.append(envelope)
        else:
            # Already an envelope
            updated_events.append(event)
    
    db['eventStore'] = updated_events

def update_test_file(file_path):
    """Update a single test file"""
    print(f"Updating {file_path}...")
    
    with open(file_path, 'r') as f:
        content = json.load(f)
    
    if 'tests' not in content:
        print(f"  No tests found in {file_path}")
        return
    
    updated = False
    for test in content['tests']:
        if 'then' in test:
            given_envelope = test.get('given', {}).get('envelope')
            old_then = json.dumps(test['then'])
            update_eventstore_in_then(test['then'], given_envelope)
            new_then = json.dumps(test['then'])
            if old_then != new_then:
                updated = True
    
    if updated:
        with open(file_path, 'w') as f:
            json.dump(content, f, indent=2)
        print(f"  ✓ Updated {file_path}")
    else:
        print(f"  No changes needed in {file_path}")

def main():
    # Find all handler test files
    test_files = []
    
    # Message via tor protocol
    msg_handlers = Path("protocols/message_via_tor/handlers")
    if msg_handlers.exists():
        for handler_dir in msg_handlers.iterdir():
            if handler_dir.is_dir():
                json_files = list(handler_dir.glob("*_handler.json"))
                test_files.extend(json_files)
    
    # Framework tests
    fw_handlers = Path("protocols/framework_tests/handlers")
    if fw_handlers.exists():
        for handler_dir in fw_handlers.iterdir():
            if handler_dir.is_dir():
                json_files = list(handler_dir.glob("*_handler.json"))
                test_files.extend(json_files)
    
    print(f"Found {len(test_files)} test files to check")
    
    for test_file in test_files:
        update_test_file(test_file)
    
    print("\nDone! Run tests again to see if they pass.")

if __name__ == "__main__":
    main()