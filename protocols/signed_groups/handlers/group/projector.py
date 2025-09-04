def project(db, envelope, time_now_ms):
    """
    Project group events to SQL (dict-state deprecated).
    Performs minimal validation via SQL when available.
    """
    data = envelope.get('data', {})
    if data.get('type') != 'group':
        return db

    group_id = data.get('id')
    name = data.get('name')
    created_by = data.get('user_id')
    signature = data.get('signature')
    if not all([group_id, name, created_by, signature]):
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    # Validate creator via SQL only
    try:
        cur = db.conn.cursor()
        u = cur.execute("SELECT 1 FROM users WHERE id = ? LIMIT 1", (created_by,)).fetchone()
        # Dummy signature check: ensure signer matches claimed user
        if signature.startswith("dummy_sig_signed_by_"):
            signer_id = signature.replace("dummy_sig_signed_by_", "")
            if signer_id != created_by:
                u = None
    except Exception:
        u = None
    if not u:
        return db

    # Persist to SQL
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO groups(id, name, created_by, created_at_ms)
                VALUES(?, ?, ?, ?)
                """,
                (group_id, name, created_by, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    # Attempt to enqueue rechecks (no-op without blocked index)
    try:
        unblock(db, group_id)
    except Exception:
        pass

    return db

def unblock(db, event_id):
    """
    Enqueue recheck markers for events blocked on this dependency (SQLite table).
    """
    cursor = getattr(db, 'conn', None).cursor() if hasattr(db, 'conn') else None
    if cursor is not None:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO recheck_queue(event_id, reason_type, available_at_ms) VALUES(?, ?, ?)",
                (event_id, None, 0)
            )
            db.conn.commit()
        except Exception:
            pass
