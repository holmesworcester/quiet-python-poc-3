def execute(params, db):
    """
    Lists all blocked events
    """
    state = db.get('state', {})
    blocked = state.get('blocked', [])
    
    return {
        'api_response': {
            'blocked': blocked
        }
    }