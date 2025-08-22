def tick(db, incoming_queue, current_identity):
    """
    Main event loop - drains incoming queue and processes events.
    """
    from .process_incoming import process_incoming
    from .adapter_graph import adapt_envelope
    from core.handler_discovery import get_handler_path
    import os
    
    # Handle 'incoming' field in db (from tests)
    if "incoming" in db:
        incoming_queue.extend(db.pop("incoming"))
    
    processed = 0
    errors = []
    
    while incoming_queue:
        envelope = incoming_queue.pop(0)
        try:
            process_incoming(envelope, db, current_identity)
            processed += 1
        except Exception as e:
            # Errors are already handled in process_incoming
            errors.append(str(e))
            continue
    
    # Process commands if present (for tests)
    if "commands" in db:
        commands = db.pop("commands")
        for cmd in commands:
            try:
                # Execute command
                handler = cmd["handler"]
                command = cmd["command"]
                input_data = cmd.get("input", {})
                
                # Load command module
                import importlib.util
                
                # Determine handler base path (for tests vs production)
                handler_base = os.environ.get("HANDLER_PATH", "handlers")
                module_path = get_handler_path(handler, command, handler_base)
                
                if not module_path:
                    raise ValueError(f"Handler command not found: {handler}/{command}")
                
                spec = importlib.util.spec_from_file_location(command, module_path)
                command_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(command_module)
                
                # Execute command
                result = command_module.execute(input_data, current_identity, db)
                
                # Process newly created events
                if "newlyCreatedEvents" in result:
                    for envelope in result["newlyCreatedEvents"]:
                        # Process through adapter graph to outgoing
                        current = envelope
                        
                        # If plaintext and needs encryption, process through full path
                        if envelope.get("envelope") == "plaintext" and input_data.get("encrypt"):
                            # plaintext -> signed
                            current = adapt_envelope(current, "signed", db, current_identity)
                            if current:
                                # signed -> encrypted
                                current = adapt_envelope(current, "encrypted", db, current_identity)
                                if current:
                                    # encrypted -> outgoing
                                    current = adapt_envelope(current, "outgoing", db, current_identity)
                        else:
                            # Normal path: plaintext -> signed -> outgoing
                            current = adapt_envelope(current, "signed", db, current_identity)
                            if current:
                                current = adapt_envelope(current, "outgoing", db, current_identity)
                        
                        # Add to outgoing queue
                        if current and current.get("envelope") == "outgoing":
                            if "outgoing" not in db:
                                db["outgoing"] = []
                            db["outgoing"].append(current)
                
            except Exception as e:
                errors.append(f"Command error: {str(e)}")
                continue
    
    # Always set incoming to empty list after processing
    db["incoming"] = []
    
    # Initialize state if not present (for tests)
    if "state" not in db:
        db["state"] = {}
    
    return processed


# Export crypto functions for framework use
from .crypto import (
    sign, verify, encrypt, decrypt, hash, seal, unseal, kdf,
    get_keypair, get_crypto_mode
)

__all__ = [
    'tick', 
    'sign', 'verify', 'encrypt', 'decrypt', 'hash', 'seal', 'unseal', 'kdf',
    'get_keypair', 'get_crypto_mode'
]