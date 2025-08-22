def execute(input_data, identity, db):
    """
    Purge old unknown events to prevent unbounded growth.
    Removes events older than the specified cutoff time.
    """
    # Get cutoff time from input or default to 24 hours
    cutoff_hours = input_data.get('cutoff_hours', 24)
    current_time = input_data.get('current_time_ms')
    
    # Check if we have any unknown events
    unknown_events = db.get('state', {}).get('unknown_events', [])
    if not unknown_events:
        return {
            "return": "No unknown events",
            "purged": 0
        }
    
    if current_time is None:
        return {
            "return": "No current time provided",
            "purged": 0
        }
    
    # Calculate cutoff time in milliseconds
    cutoff_time = current_time - (cutoff_hours * 60 * 60 * 1000)
    
    # Count events before purging
    before_count = len(unknown_events)
    
    # Filter out old events
    db['state']['unknown_events'] = [
        event for event in unknown_events
        if event.get('timestamp', 0) > cutoff_time
    ]
    
    # Count purged events
    after_count = len(db['state']['unknown_events'])
    purged_count = before_count - after_count
    
    return {
        "return": f"Purged {purged_count} events",
        "purged": purged_count,
        "remaining": after_count
    }