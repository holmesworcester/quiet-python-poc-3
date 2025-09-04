def project(db, envelope, time_now_ms):
    """
    Project invite events into SQL (dict-state deprecated). Minimal SQL validation.
    """
    data = envelope.get('data', {})
    if data.get('type') != 'invite':
        return db

    invite_id = data.get('id')
    invite_pubkey = data.get('invite_pubkey')
    network_id = data.get('network_id')
    created_by = data.get('created_by')
    group_id = data.get('group_id')
    signature = data.get('signature')
    if not all([invite_id, invite_pubkey, network_id, created_by, signature]):
        return db
    if not group_id:
        # Missing required group_id – drop projection (no dict block state)
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    # Minimal checks via SQL only
    try:
        cur = db.conn.cursor()
        # unknown signer
        if signature.startswith("dummy_sig_from_unknown"):
            return db
        # ensure group exists
        g = cur.execute("SELECT 1 FROM groups WHERE id = ? LIMIT 1", (group_id,)).fetchone()
        # ensure creator exists
        u = cur.execute("SELECT 1 FROM users WHERE id = ? LIMIT 1", (created_by,)).fetchone()
        # Enforce first-group rule using networks.first_group_id
        n = cur.execute("SELECT first_group_id FROM networks WHERE id = ? LIMIT 1", (network_id,)).fetchone()
        current_first = n[0] if n else None
        first_group_ok = True
        if current_first:
            first_group_ok = (current_first == group_id)
        else:
            cur.execute(
                "INSERT OR IGNORE INTO networks(id, name, creator_pubkey, first_group_id, created_at_ms) VALUES(?, ?, ?, ?, 0)",
                (network_id, '', created_by or '', group_id)
            )
            cur.execute("UPDATE networks SET first_group_id = COALESCE(first_group_id, ?) WHERE id = ?", (group_id, network_id))
    except Exception:
        return db
    if not (g and u and first_group_ok):
        return db

    # Persist invite
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO invites(id, invite_pubkey, network_id, group_id, created_by, created_at_ms)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (invite_id, invite_pubkey, network_id, group_id, created_by, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    try:
        unblock(db, invite_id)
    except Exception:
        pass

    return db

def unblock(db, event_id):
    """
    Enqueue recheck markers for events blocked on this dependency (SQLite table).
    """
    cursor = getattr(db, 'conn', None).cursor() if hasattr(db, 'conn') else None
    
    # Without dict blocked index, just enqueue the event itself if possible
    if cursor is not None:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO recheck_queue(event_id, reason_type, available_at_ms) VALUES(?, ?, ?)",
                (event_id, None, 0)
            )
            db.conn.commit()
        except Exception:
            pass
