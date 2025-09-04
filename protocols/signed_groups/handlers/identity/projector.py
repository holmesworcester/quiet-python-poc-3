def project(db, envelope, time_now_ms):
    """
    Project identity events to SQL (dict-state deprecated).
    """
    data = envelope.get('data', {})
    if data.get('type') != 'identity':
        return db

    pubkey = data.get('pubkey')
    privkey = data.get('privkey')
    name = data.get('name') or (pubkey[:8] if pubkey else None)
    if not pubkey or not privkey:
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
                INSERT OR IGNORE INTO identities(pubkey, privkey, name, created_at_ms)
                VALUES(?, ?, ?, ?)
                """,
                (pubkey, privkey, name, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    return db
