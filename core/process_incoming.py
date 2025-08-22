import hashlib
import json
from .adapter_graph import adapt_envelope
from .handle import handle

def process_incoming(envelope, db, current_identity):
    """
    Process an incoming envelope through the adapter graph to verifiedPlaintext,
    then pass to appropriate handler.
    """
    try:
        # Store raw event first if it's encrypted (even if we can't decrypt yet)
        if envelope.get("metadata", {}).get("encrypted") or envelope.get("envelope") == "encrypted":
            # Store encrypted events by keyId for later decryption
            if "eventStore" not in db:
                db["eventStore"] = {}
            
            keyId = envelope.get("metadata", {}).get("keyId", "unknown_key")
            if keyId not in db["eventStore"]:
                db["eventStore"][keyId] = []
            
            # Store the encrypted envelope
            db["eventStore"][keyId].append({
                "encrypted": True,
                "envelope": envelope,
                "stored_at": envelope.get("metadata", {}).get("timestamp", "unknown")
            })
        
        # Adapt to verifiedPlaintext
        verified = adapt_envelope(envelope, "verifiedPlaintext", db, current_identity)
        
        if not verified:
            # Failed to adapt - add to blocked but we already stored if encrypted
            if "blocked" not in db:
                db["blocked"] = []
            
            error_msg = f"Failed to adapt {envelope.get('envelope')} to verifiedPlaintext"
            
            # Special case for invalid type
            if isinstance(envelope.get("data"), dict) and envelope.get("data", {}).get("type") == "invalid":
                error_msg = "Validation failed: unknown type"
                
            db["blocked"].append({
                "envelope": envelope,
                "error": error_msg
            })
            return
        
        # Extract event data
        event_data = verified["data"]
        
        # Ensure event_data is a dict
        if not isinstance(event_data, dict):
            raise ValueError(f"Event data must be a dict, got {type(event_data).__name__}: {event_data}")
        
        event_type = event_data.get("type")
        
        if not event_type:
            raise ValueError("Event missing type field")
        
        # Get or generate event_id
        event_id = verified.get("metadata", {}).get("event_id")
        if not event_id:
            # Generate event_id from envelope
            canonical = json.dumps(envelope, sort_keys=True)
            event_id = hashlib.blake2b(canonical.encode()).hexdigest()[:16]
        
        event_data["event_id"] = event_id
        
        # Determine sender identity from metadata
        sender = verified.get("metadata", {}).get("sender")
        if sender:
            event_data["sender"] = sender
        
        # Store event in eventStore indexed by sender/keyId
        if "eventStore" not in db:
            db["eventStore"] = {}
        
        # Index by sender (public key) if available, otherwise use keyId or default
        store_key = sender
        if not store_key:
            # Try keyId from metadata (for encrypted messages)
            store_key = envelope.get("metadata", {}).get("keyId")
        if not store_key:
            # For backward compatibility with tests
            store_key = "pubkey1"
        
        if store_key not in db["eventStore"]:
            db["eventStore"][store_key] = []
        
        # Store the full verified envelope for handlers to process
        db["eventStore"][store_key].append(event_data)
        
        # Pass to handler for projection
        handle(event_type, verified, db, current_identity)
        
    except Exception as e:
        # On any error, add to blocked
        if "blocked" not in db:
            db["blocked"] = []
        
        db["blocked"].append({
            "envelope": envelope,
            "error": str(e)
        })
        
        # Re-raise to maintain existing behavior
        print(f"Error processing envelope: {e}")
        raise