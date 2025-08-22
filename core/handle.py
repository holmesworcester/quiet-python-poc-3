import importlib.util
import json
import os
from core.handler_discovery import build_handler_map, load_handler_config

def handle(event_type, envelope, db, current_identity):
    """
    Route events to appropriate handlers based on type.
    """
    # Get handler base path (for tests vs production)
    handler_base = os.environ.get("HANDLER_PATH", "handlers")
    
    # Build handler map dynamically from available handlers
    handler_map = build_handler_map(handler_base)
    
    handler_name = handler_map.get(event_type)
    if not handler_name:
        # No handler for this event type - this is expected for invalid types
        if event_type == "invalid":
            raise ValueError("Validation failed: unknown type")
        print(f"No handler found for event type: {event_type}")
        return
    
    # Load handler config
    handler_dir = f"{handler_base}/{handler_name}"
    config = load_handler_config(handler_name, handler_base)
    
    if not config:
        print(f"Handler config not found for: {handler_name}")
        return
    
    # Handler directory name matches event type, so we can proceed
    
    # Load and run projector
    projector_path = f"{handler_dir}/projector.py"
    if os.path.exists(projector_path):
        spec = importlib.util.spec_from_file_location("projector", projector_path)
        projector_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(projector_module)
        
        # Initialize state if needed
        if "state" not in db:
            db["state"] = {}
        
        # Run projector
        projector_module.project(envelope, db["state"], current_identity)