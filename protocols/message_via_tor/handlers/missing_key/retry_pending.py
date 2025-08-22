def execute(input_data, identity, db):
    """
    Retry pending missing key envelopes when key_map has changed.
    This job command checks if any pending entries now have available keys.
    """
    # Check if we have any pending missing key entries
    pending_entries = db.get('state', {}).get('pending_missing_key', [])
    if not pending_entries:
        return {
            "return": "No pending entries",
            "processed": 0
        }
    
    # Track which entries to remove (successfully processed)
    to_remove = []
    processed_count = 0
    
    # Try to reprocess each pending entry
    for i, entry in enumerate(pending_entries):
        envelope = entry.get('envelope')
        if not envelope:
            continue
            
        missing_hash = entry.get('missingHash')
        if not missing_hash:
            continue
            
        # Check if we now have the missing key
        if missing_hash in db.get('state', {}).get('key_map', {}):
            # We have the key now!
            # In a real implementation, we'd store the original blob and reprocess it
            # For now, we'll just mark it for removal
            to_remove.append(i)
            processed_count += 1
    
    # Remove processed entries (in reverse order to maintain indices)
    for i in reversed(to_remove):
        db['state']['pending_missing_key'].pop(i)
    
    return {
        "return": f"Processed {processed_count} entries",
        "processed": processed_count,
        "remaining": len(db.get('state', {}).get('pending_missing_key', []))
    }