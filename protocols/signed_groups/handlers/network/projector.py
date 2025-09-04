def project(db, envelope, time_now_ms):
    """
    Project network events into SQL (dict-state deprecated).
    """
    data = envelope.get('data', {})
    if data.get('type') != 'network':
        return db

    network_id = data.get('id')
    name = data.get('name')
    creator_pubkey = data.get('creator_pubkey')
    if not network_id or not name or not creator_pubkey:
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    # Persist to SQL
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO networks(id, name, creator_pubkey, created_at_ms)
                VALUES(?, ?, ?, ?)
                """,
                (network_id, name, creator_pubkey, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    return db
