def execute(params, db):
    """
    Drain recheck markers and re-process affected events using SQL event_store.
    """
    import os
    import json as _json
    time_now_ms = params.get('time_now_ms', 1000)
    cursor = getattr(db, 'conn', None).cursor() if hasattr(db, 'conn') else None

    # Optional: acquire a lightweight lease to avoid multiple drainers
    try:
        if hasattr(db, 'conn') and params.get('time_now_ms') is not None:
            from core.lease import acquire_lease
            now_ms = int(params.get('time_now_ms') or 0)
            # Short TTL; job runs frequently
            acquired = acquire_lease(db.conn, 'signed_groups.blocked.process_unblocked', 'job', now_ms, 2000)
            if not acquired:
                return {"processed": 0}
    except Exception:
        # If lease infra is unavailable, proceed without it
        pass
    
    # Load up to 1000 markers
    if cursor is not None:
        rows = cursor.execute(
            "SELECT event_id FROM recheck_queue ORDER BY available_at_ms LIMIT 1000"
        ).fetchall()
        event_ids_to_process = [row[0] for row in rows]
        if os.environ.get("TEST_MODE"):
            print(f"[blocked.process_unblocked] Draining markers: {event_ids_to_process}")
    else:
        # No SQL connection; nothing to do
        return {"processed": 0}
    
    # If no markers, nothing to do
    if not event_ids_to_process:
        return {"processed": 0}

    # Remove all markers we're about to process
    try:
        cursor.execute("DELETE FROM recheck_queue")
        db.conn.commit()
    except Exception:
        pass

    # Replay all events idempotently from SQL event_store
    processed = 0
    try:
        rows = cursor.execute("SELECT data, metadata FROM event_store ORDER BY id").fetchall()
        from core.handle import handle
        for row in rows:
            try:
                data = row[0]
                metadata = row[1]
                try:
                    data = _json.loads(data) if isinstance(data, (bytes, str)) else data
                except Exception:
                    pass
                try:
                    metadata = _json.loads(metadata) if isinstance(metadata, (bytes, str)) else (metadata or {})
                except Exception:
                    metadata = {}
                db = handle(db, { 'data': data, 'metadata': metadata }, time_now_ms, auto_transaction=False)
                processed += 1
            except Exception as e:
                if os.environ.get("TEST_MODE"):
                    print(f"[blocked.job] Failed to re-process event: {e}")
                continue
    except Exception:
        pass

    return {"processed": processed}
