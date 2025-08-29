def project(db, envelope, time_now_ms):
    """
    This projector doesn't handle specific events but ensures blocked state exists.
    Other projectors will add to the blocked list when they encounter invalid events.
    """
    if 'state' not in db:
        db['state'] = {}
    
    if 'blocked' not in db['state']:
        db['state']['blocked'] = []
    
    # This handler doesn't process specific events
    # It just ensures the blocked list exists for other handlers to use
    
    return db