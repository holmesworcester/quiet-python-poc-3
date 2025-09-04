def project(db, envelope, time_now_ms):
    """
    Project link events into SQL (dict-state deprecated).
    """
    data = envelope.get('data', {})
    if data.get('type') != 'link':
        return db

    link_id = data.get('id')
    peer_id = data.get('peer_id')
    user_id = data.get('user_id')
    link_invite_id = data.get('link_invite_id')
    link_invite_signature = data.get('link_invite_signature')
    signature = data.get('signature')
    if not all([link_id, peer_id, user_id, link_invite_id, link_invite_signature, signature]):
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    if hasattr(db, 'conn'):
        try:
            cur = db.conn.cursor()
            # Signature must be from peer
            if signature.startswith("dummy_sig_signed_by_"):
                signer_id = signature.replace("dummy_sig_signed_by_", "")
                if signer_id != peer_id:
                    return db
            # Ensure link_invite exists and matches user
            li = cur.execute("SELECT user_id FROM link_invites WHERE id = ?", (link_invite_id,)).fetchone()
            if not li:
                return db
            if li[0] != user_id:
                return db
        except Exception:
            return db

    # Persist to SQL
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO links(id, peer_id, user_id, link_invite_id, created_at_ms)
                VALUES(?, ?, ?, ?, ?)
                """,
                (link_id, peer_id, user_id, link_invite_id, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    try:
        unblock(db, link_id)
        unblock(db, peer_id)
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
