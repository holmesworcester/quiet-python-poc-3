def project(db, envelope, time_now_ms):
    """
    Project message events to SQL (dict-state deprecated). Minimal validation.
    """
    data = envelope.get('data', {})
    if data.get('type') != 'message':
        return db

    message_id = data.get('id')
    channel_id = data.get('channel_id')
    author_id = data.get('author_id')
    peer_id = data.get('peer_id')
    user_id = data.get('user_id')
    content = data.get('content') or data.get('text')
    signature = data.get('signature')
    if not all([message_id, channel_id, author_id, content, signature, peer_id]):
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    # Minimal validations: signature must match peer_id; peer must be linked to user when different
    try:
        # Signature check
        if signature.startswith("dummy_sig_signed_by_"):
            signer = signature.replace("dummy_sig_signed_by_", "")
            if signer != str(peer_id):
                return db
        # Link check (allow self-messages where peer_id == user_id)
        if peer_id and user_id and peer_id != user_id:
            try:
                cur = db.conn.cursor()
                row = cur.execute(
                    "SELECT 1 FROM links WHERE peer_id = ? AND user_id = ? LIMIT 1",
                    (peer_id, user_id)
                ).fetchone()
                if not row:
                    return db
            except Exception:
                return db
    except Exception:
        return db

    # Persist to SQL
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO messages(id, channel_id, author_id, peer_id, user_id, content, created_at_ms)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, channel_id, author_id, peer_id, user_id, content, int(time_now_ms or 0))
            )
            db.conn.commit()
    except Exception:
        pass

    return db
