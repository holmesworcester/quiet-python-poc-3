def execute(params, db):
    """
    Lists all blocked events
    """
    state = db.get('state', {})
    blocked_by_id = state.get('blocked_by_id', {})
    
    # Flatten the blocked_by_id structure into a list
    blocked = []
    for blocker_id, events in blocked_by_id.items():
        for event in events:
            blocked.append({
                'event_id': event['event_id'],
                'blocked_by': blocker_id,
                'reason': event['reason']
            })
    
    return {
        'api_response': {
            'blocked': blocked
        }
    }