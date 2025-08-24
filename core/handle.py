import importlib.util
import os
from core.handler_discovery import build_handler_map, load_handler_config


def handle(db, envelope, time_now_ms):
    """
    Route envelopes to appropriate handlers based on type or error state.
    """
    try:
        # Check for error in metadata (missing key scenario)
        if 'error' in envelope.get('metadata', {}):
            event_type = 'missing_key'
        else:
            # Get event type from data
            event_type = envelope.get('data', {}).get('type')
            if not event_type:
                event_type = 'unknown'
        
        # Log what we're handling
        if os.environ.get("TEST_MODE"):
            print(f"[handle] Processing event type: {event_type}")
        
        # Get handler base path (for tests vs production)
        handler_base = os.environ.get("HANDLER_PATH", "handlers")
        
        # Build handler map dynamically from available handlers
        handler_map = build_handler_map(handler_base)
        
        handler_name = handler_map.get(event_type)
        
        # Log handler mapping
        if os.environ.get("TEST_MODE"):
            print(f"[handle] Handler map: {handler_map}")
            print(f"[handle] Selected handler: {handler_name} for type: {event_type}")
        
        if not handler_name:
            # Route to unknown handler for unrecognized types
            handler_name = handler_map.get('unknown')
            if not handler_name:
                # If no unknown handler, add to blocked with expected error message
                db.setdefault('blocked', []).append({
                    'envelope': envelope,
                    'error': 'Validation failed: unknown type'
                })
                return db
        
        # Load handler config
        handler_dir = f"{handler_base}/{handler_name}"
        config = load_handler_config(handler_name, handler_base)
        
        if not config:
            db.setdefault('blocked', []).append({
                'envelope': envelope,
                'error': f'Handler config not found for: {handler_name}'
            })
            return db
        
        # Load and run projector
        projector_path = f"{handler_dir}/projector.py"
        if os.path.exists(projector_path):
            spec = importlib.util.spec_from_file_location("projector", projector_path)
            projector_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(projector_module)
            
            # Initialize state if needed
            if "state" not in db:
                db["state"] = {}
            
            # Run projector with full envelope
            result = projector_module.project(db, envelope, time_now_ms)
            if result is not None:
                db = result
            
        else:
            db.setdefault('blocked', []).append({
                'envelope': envelope,
                'error': f'Projector not found for handler: {handler_name}'
            })
            
    except Exception as e:
        db.setdefault('blocked', []).append({
            'envelope': envelope,
            'error': str(e)
        })
    
    return db