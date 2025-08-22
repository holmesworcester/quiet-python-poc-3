import os
import sys
import json
import hashlib
import importlib.util
from collections import deque

# Global adapter registry
ADAPTERS = {}
ADAPTER_GRAPH = {}
ENVELOPE_SCHEMAS = {}

# Flag to indicate if running in test mode
TEST_MODE = False

def load_adapters_from_envelopes(base_path):
    """Load all adapters from envelope subdirectories"""
    global ADAPTERS, ADAPTER_GRAPH, ENVELOPE_SCHEMAS
    
    ADAPTERS.clear()
    ADAPTER_GRAPH.clear()
    ENVELOPE_SCHEMAS.clear()
    
    envelopes_dir = os.path.join(base_path, "envelopes")
    if not os.path.exists(envelopes_dir):
        return
    
    # Discover all envelope types
    for envelope_name in os.listdir(envelopes_dir):
        envelope_dir = os.path.join(envelopes_dir, envelope_name)
        if not os.path.isdir(envelope_dir):
            continue
            
        # Load envelope definition if exists
        envelope_path = os.path.join(envelope_dir, "envelope.json")
        if os.path.exists(envelope_path):
            with open(envelope_path, 'r') as f:
                ENVELOPE_SCHEMAS[envelope_name] = json.load(f)
        
        # Load adapters from adapters subdirectory
        adapters_dir = os.path.join(envelope_dir, "adapters")
        if os.path.exists(adapters_dir):
            for filename in os.listdir(adapters_dir):
                if filename.endswith('.py') and '_to_' in filename:
                    filepath = os.path.join(adapters_dir, filename)
                    
                    # Load the module
                    spec = importlib.util.spec_from_file_location(filename[:-3], filepath)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Get adapter metadata
                    if hasattr(module, 'ADAPTER'):
                        adapter_info = module.ADAPTER
                        from_type = adapter_info['from']
                        to_type = adapter_info['to']
                        adapter_func = adapter_info['function']
                        
                        # Register adapter
                        adapter_name = f"{from_type}_to_{to_type}"
                        
                        # Check for duplicate adapters
                        if adapter_name in ADAPTERS:
                            raise ValueError(
                                f"Duplicate adapter found: {adapter_name}. "
                                f"There should only be one canonical adapter per transformation. "
                                f"Consider creating shortcut adapters for multi-hop transformations instead."
                            )
                        
                        ADAPTERS[adapter_name] = adapter_func
                        
                        # Build graph
                        if from_type not in ADAPTER_GRAPH:
                            ADAPTER_GRAPH[from_type] = []
                        if to_type not in ADAPTER_GRAPH[from_type]:
                            ADAPTER_GRAPH[from_type].append(to_type)


def find_adapter_path(from_type, to_type):
    """Find a path of adapters from one envelope type to another"""
    if from_type == to_type:
        return []
    
    # BFS to find shortest path
    queue = deque([(from_type, [from_type])])
    visited = {from_type}
    
    while queue:
        current, path = queue.popleft()
        
        for next_type in ADAPTER_GRAPH.get(current, []):
            if next_type == to_type:
                return path + [next_type]
            
            if next_type not in visited:
                visited.add(next_type)
                queue.append((next_type, path + [next_type]))
    
    return None

def find_all_adapter_paths(from_type, to_type, max_depth=5):
    """Find all possible paths from one envelope type to another"""
    if from_type == to_type:
        return [[from_type]]
    
    all_paths = []
    
    def dfs(current, path, visited):
        if len(path) > max_depth:
            return
        
        if current == to_type:
            all_paths.append(path[:])
            return
        
        for next_type in ADAPTER_GRAPH.get(current, []):
            if next_type not in visited:
                visited.add(next_type)
                path.append(next_type)
                dfs(next_type, path, visited)
                path.pop()
                visited.remove(next_type)
    
    dfs(from_type, [from_type], {from_type})
    return all_paths

def apply_adapter(from_type, to_type, envelope, db, identity):
    """Apply a specific adapter"""
    adapter_name = f"{from_type}_to_{to_type}"
    adapter = ADAPTERS.get(adapter_name)
    
    if adapter:
        return adapter(envelope, db, identity)
    
    return None

def adapt_envelope(envelope, target_type, db, current_identity):
    """
    Transform envelope between different types using the adapter graph.
    Dynamically loads adapters from the configured path.
    """
    # Validate envelope is a dict
    if not isinstance(envelope, dict):
        return None
    
    # Load adapters if not already loaded
    # Adapters should be pre-loaded by the application or test runner
    if not ADAPTERS:
        # In production, load from current directory
        # Test runner should have already loaded test adapters
        load_adapters_from_envelopes(".")
    
    current_type = envelope.get("envelope")
    
    if current_type == target_type:
        return envelope
    
    # Special case: for incoming envelopes, try direct adapters first
    if current_type == "incoming":
        # Try direct adapter if available
        direct_result = apply_adapter(current_type, target_type, envelope, db, current_identity)
        if direct_result:
            return direct_result
    
    # Find all possible paths
    all_paths = find_all_adapter_paths(current_type, target_type)
    if not all_paths:
        return None
    
    # Sort paths by length (shortest first)
    all_paths.sort(key=len)
    
    # Try each path until one works
    for path in all_paths:
        result = envelope
        success = True
        
        for i in range(len(path) - 1):
            from_type = path[i]
            to_type = path[i + 1]
            
            result = apply_adapter(from_type, to_type, result, db, current_identity)
            if not result:
                success = False
                break
        
        if success and result:
            return result
    
    return None