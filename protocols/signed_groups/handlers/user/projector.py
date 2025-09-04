def project(db, envelope, time_now_ms):
    """
    Project user events into SQL (dict-state deprecated). Minimal SQL validation.
    """
    data = envelope.get('data', {})
    if data.get('type') != 'user':
        return db

    user_id = data.get('id')
    network_id = data.get('network_id')
    pubkey = data.get('pubkey')
    name = data.get('name')
    invite_id = data.get('invite_id')
    group_id = data.get('group_id')
    signature = data.get('signature')

    if not all([user_id, network_id, pubkey, name, signature]):
        return db

    # Append to SQL event_store (protocol-owned)
    try:
        from .._event_store import append as _append_event
        _append_event(db, envelope, time_now_ms)
    except Exception:
        pass

    # Basic SQL validations
    if hasattr(db, 'conn'):
        try:
            cur = db.conn.cursor()
            # If signature unknown, allow only if network creator
            if signature.startswith("dummy_sig_from_unknown"):
                creator = cur.execute(
                    "SELECT creator_pubkey FROM networks WHERE id = ? LIMIT 1",
                    (network_id,)
                ).fetchone()
                if not creator or (creator[0] != pubkey):
                    return db

            if invite_id:
                # group_id must be present when joining via invite
                if not group_id:
                    return db
                # invite must exist
                inv = cur.execute("SELECT 1 FROM invites WHERE id = ? LIMIT 1", (invite_id,)).fetchone()
                if not inv:
                    return db
                # Enforce first-group rule when known
                try:
                    nrow = cur.execute("SELECT first_group_id FROM networks WHERE id = ? LIMIT 1", (network_id,)).fetchone()
                    current_first = nrow[0] if nrow else None
                    if current_first:
                        if current_first != group_id:
                            return db
                    else:
                        # If unknown, set it now based on this invite usage
                        cur.execute("UPDATE networks SET first_group_id = ? WHERE id = ?", (group_id, network_id))
                        db.conn.commit()
                except Exception:
                    pass
            else:
                # Not network creator and no invite: invalid
                creator = cur.execute(
                    "SELECT creator_pubkey FROM networks WHERE id = ? LIMIT 1",
                    (network_id,)
                ).fetchone()
                if not creator or (creator[0] != pubkey):
                    return db
        except Exception:
            return db

    # Persist user
    try:
        if hasattr(db, 'conn'):
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO users(id, network_id, pubkey, name, group_id, invite_id, created_at_ms)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    network_id,
                    pubkey,
                    name,
                    group_id,
                    invite_id,
                    int(time_now_ms or 0)
                )
            )
            db.conn.commit()
    except Exception:
        pass

    try:
        unblock(db, user_id)
    except Exception:
        pass

    return db

def unblock(db, event_id):
    """
    Enqueue recheck markers for events blocked on this dependency (SQLite table).
    """
    cursor = getattr(db, 'conn', None).cursor() if hasattr(db, 'conn') else None
    # Without dict-state, enqueue this event for recheck if possible
    if cursor is not None:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO recheck_queue(event_id, reason_type, available_at_ms) VALUES(?, ?, ?)",
                (event_id, None, 0)
            )
            db.conn.commit()
        except Exception:
            pass
