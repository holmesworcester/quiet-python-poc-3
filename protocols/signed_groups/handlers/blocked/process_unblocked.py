def execute(params, db):
    """
    Process events marked as ready_to_unblock
    """
    import os
    time_now_ms = params.get('time_now_ms', 1000)
    state = db.get('state', {})
    ready_to_unblock = state.get('ready_to_unblock', {})
    blocked_by_id = state.get('blocked_by_id', {})
    event_store = db.get('eventStore', [])
    
    if os.environ.get("TEST_MODE"):
        print(f"[blocked.process_unblocked] Running with ready_to_unblock: {ready_to_unblock}")
    
    if not ready_to_unblock:
        return {"processed": 0}
    
    # Process up to 1000 events per tick for performance
    event_ids_to_process = list(ready_to_unblock.keys())[:1000]
    
    for event_id in event_ids_to_process:
        # Begin transaction for this one event (only for persistent db)
        has_transactions = hasattr(db, 'begin_transaction')
        if has_transactions:
            db.begin_transaction()
        
        try:
            # Remove from ready_to_unblock
            del ready_to_unblock[event_id]
            state['ready_to_unblock'] = ready_to_unblock
            
            # Remove from blocked_by_id structure
            for blocker_id, blocked_list in list(blocked_by_id.items()):
                blocked_by_id[blocker_id] = [
                    b for b in blocked_list if b['event_id'] != event_id
                ]
                # Clean up empty lists
                if not blocked_by_id[blocker_id]:
                    del blocked_by_id[blocker_id]
            state['blocked_by_id'] = blocked_by_id
            
            
            # Update db state
            db['state'] = state
            
            # Find the event in eventStore
            envelope_to_process = None
            for envelope in event_store:
                if envelope.get('data', {}).get('id') == event_id:
                    envelope_to_process = envelope
                    break
            
            if envelope_to_process:
                # Re-process the event
                from core.handle import handle
                if os.environ.get("TEST_MODE"):
                    print(f"[blocked.process_unblocked] Re-processing event {event_id}")
                db = handle(db, envelope_to_process, time_now_ms, auto_transaction=False)
                
                # Re-read state after handle
                state = db.get('state', {})
                ready_to_unblock = state.get('ready_to_unblock', {})
                blocked_by_id = state.get('blocked_by_id', {})
            
            # Commit the transaction
            if has_transactions:
                db.commit()
                
        except Exception as e:
            # Rollback on error
            if has_transactions:
                db.rollback()
            
            # Re-add to ready_to_unblock for retry
            ready_to_unblock[event_id] = True
            state['ready_to_unblock'] = ready_to_unblock
            db['state'] = state
            
            # Log the error if in test mode
            if os.environ.get("TEST_MODE"):
                print(f"[blocked.job] Failed to process unblocked event {event_id}: {e}")
    
    return {"processed": len(event_ids_to_process)}