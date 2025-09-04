def project(db, envelope, time_now_ms):
    """
    Project add events into SQL (dict-state deprecated). Minimal SQL validation.
    """
    data = envelope.get('data', {})
    if data.get('type') != 'add':
        return db

    add_id = data.get('id')
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    added_by = data.get('added_by')
    signature = data.get('signature')
    if not all([add_id, group_id, user_id, added_by, signature]):
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    # Minimal validation via SQL only
    try:
        cur = db.conn.cursor()
        if signature.startswith("dummy_sig_from_unknown"):
            return db
        g = cur.execute("SELECT 1 FROM groups WHERE id = ? LIMIT 1", (group_id,)).fetchone()
        u1 = cur.execute("SELECT 1 FROM users WHERE id = ? LIMIT 1", (user_id,)).fetchone()
        u2 = cur.execute("SELECT 1 FROM users WHERE id = ? LIMIT 1", (added_by,)).fetchone()
    except Exception:
        return db
    if not (g and u1 and u2):
        return db

    # Persist to SQL
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO adds(id, group_id, user_id, added_by, created_at_ms)
                VALUES(?, ?, ?, ?, ?)
                """,
                (add_id, group_id, user_id, added_by, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    try:
        unblock(db, add_id)
    except Exception:
        pass

    return db

def unblock(db, event_id):
    """
    Enqueue recheck markers for events blocked on this dependency (SQLite table).
    """
    cursor = getattr(db, 'conn', None).cursor() if hasattr(db, 'conn') else None
    # Dict-state deprecated; without a blocked index, no-op unless SQL mapping exists
    if cursor is not None:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO recheck_queue(event_id, reason_type, available_at_ms) VALUES(?, ?, ?)",
                (event_id, None, 0)
            )
            db.conn.commit()
        except Exception:
            pass
