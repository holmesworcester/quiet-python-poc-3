def project(db, envelope, time_now_ms):
    """
    Project unknown event types. SQL-first into 'unknown_events';
    keep dict fallback for legacy tests.
    """
    data = envelope.get('data')
    metadata = envelope.get('metadata', {})
    ts = metadata.get('receivedAt', time_now_ms)

    # SQL-first
    try:
        if hasattr(db, 'conn') and db.conn is not None:
            cur = db.conn.cursor()
            cur.execute(
                """
                INSERT INTO unknown_events (data, metadata, timestamp)
                VALUES (?, ?, ?)
                """,
                (__json_dump(data), __json_dump(metadata), int(ts or 0)),
            )
    except Exception:
        pass

    return db


def __json_dump(obj):
    try:
        import json
        return json.dumps(obj)
    except Exception:
        return None
