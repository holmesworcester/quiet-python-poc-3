def execute(params, db):
    """
    Lists blocked/recheck markers from SQL (dict-state deprecated).
    """
    blocked = []
    cur = db.conn.cursor()
    rows = cur.execute("SELECT event_id, reason_type FROM recheck_queue ORDER BY available_at_ms").fetchall()
    for r in rows:
        blocked.append({'event_id': r[0], 'blocked_by': None, 'reason': r[1]})
    return {'api_response': {'blocked': blocked}}
