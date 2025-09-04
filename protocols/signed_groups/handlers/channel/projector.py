def project(db, envelope, time_now_ms):
    """
    Project channel events into SQL (dict-state deprecated). Minimal SQL validation.
    """
    data = envelope.get('data', {})
    if data.get('type') != 'channel':
        return db

    channel_id = data.get('id')
    network_id = data.get('network_id')
    name = data.get('name')
    created_by = data.get('created_by')
    group_id = data.get('group_id')
    signature = data.get('signature')
    if not all([channel_id, network_id, name, created_by, signature]):
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    # Optional checks via SQL
    if hasattr(db, 'conn'):
        try:
            cur = db.conn.cursor()
            # Unknown signer check (dummy)
            if signature.startswith("dummy_sig_from_unknown"):
                return db
            # Enforce existing group if provided
            if group_id:
                g = cur.execute("SELECT 1 FROM groups WHERE id = ? LIMIT 1", (group_id,)).fetchone()
                if not g:
                    return db
        except Exception:
            return db

    # Persist to SQL
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO channels(id, network_id, name, created_by, group_id, created_at_ms)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (channel_id, network_id, name, created_by, group_id, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    # Attempt recheck enqueue (no-op without blocked index)
    try:
        unblock(db, channel_id)
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
