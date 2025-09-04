import json
import uuid

def _ensure_event_id(metadata, data):
    if isinstance(metadata, dict) and metadata.get('eventId'):
        return str(metadata['eventId'])
    if isinstance(data, dict) and data.get('id'):
        return str(data['id'])
    return str(uuid.uuid4())

def append(db, envelope, time_now_ms):
    """
    Append an event envelope to the SQL event_store for signed_groups.
    """
    if not hasattr(db, 'conn') or db.conn is None:
        return
    data = envelope.get('data') or {}
    metadata = envelope.get('metadata') or {}
    event_type = data.get('type') or 'unknown'
    event_id = _ensure_event_id(metadata, data)
    try:
        cur = db.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO event_store(event_id, event_type, data, metadata, created_at_ms)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                json.dumps(data, sort_keys=True),
                json.dumps(metadata, sort_keys=True),
                int(time_now_ms or 0),
            )
        )
        db.conn.commit()
    except Exception:
        pass

