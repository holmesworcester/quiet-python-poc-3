from core.handle import handle
import uuid
import time
import json


def execute(input_data, db):
    """
    Process incoming message queue (SQL-backed).
    """
    current_time = input_data.get("time_now_ms", int(time.time() * 1000))

    # Read from SQL incoming table
    rows = []
    if hasattr(db, 'conn'):
        try:
            cur = db.conn.cursor()
            rs = cur.execute("SELECT id, recipient, data, metadata FROM incoming ORDER BY id").fetchall()
            for r in rs:
                rid = r[0]
                recipient = r[1]
                data = r[2]
                metadata = r[3]
                try:
                    data = json.loads(data) if isinstance(data, str) else data
                except Exception:
                    pass
                try:
                    metadata = json.loads(metadata) if isinstance(metadata, str) else (metadata or {})
                except Exception:
                    metadata = {}
                rows.append({"id": rid, "recipient": recipient, "data": data, "metadata": metadata})
        except Exception:
            rows = []

    # Process each envelope
    for row in rows:
        envelope = {
            "envelope": True,
            "recipient": row["recipient"],
            "data": row["data"],
            "metadata": row["metadata"] or {}
        }
        if 'eventId' not in envelope['metadata']:
            envelope['metadata']['eventId'] = str(uuid.uuid4())
        if 'timestamp' not in envelope['metadata']:
            envelope['metadata']['timestamp'] = current_time
        # Ensure received_by present
        if 'received_by' not in envelope['metadata']:
            envelope['metadata']['received_by'] = row["recipient"]

        db = handle(db, envelope, input_data.get("time_now_ms"), auto_transaction=False)

    # Delete processed rows
    if hasattr(db, 'conn') and rows:
        try:
            cur = db.conn.cursor()
            ids = [r['id'] for r in rows]
            q_marks = ','.join(['?'] * len(ids))
            cur.execute(f"DELETE FROM incoming WHERE id IN ({q_marks})", ids)
            db.conn.commit()
        except Exception:
            pass

    return {"db": db}
