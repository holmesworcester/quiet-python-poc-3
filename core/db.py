"""
SQLite-backed dictionary for persistent storage.
Provides the same dict interface as before, but with persistence.
Can use protocol-specific schema.sql files when available.
"""
import json
import os
import sqlite3
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Iterator, Dict

class PersistentDict(MutableMapping):
    """
    A dict-like object backed by SQLite for persistence.
    Maintains the same interface as dict but stores data in SQLite.
    Can optionally use a protocol's schema.sql for initialization.
    """
    
    def __init__(self, db_path=":memory:", protocol_name=None):
        """
        Initialize persistent dict.
        
        Args:
            db_path: Path to SQLite database file. Defaults to in-memory.
            protocol_name: Name of protocol to load schema.sql from (optional).
        """
        self.db_path = db_path
        self.protocol_name = protocol_name
        # Use timeout to avoid database locked errors
        self.conn = sqlite3.connect(db_path, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        # Keep it vanilla - no special pragmas for now
        # This ensures test behavior matches production
        
        # Initialize with protocol schema if available
        if protocol_name and db_path != ":memory:":
            self._init_from_protocol_schema()
        else:
            self._init_default_tables()
        
        # Cache for better performance
        self._cache = {}
        self._load_cache()
    
    def _init_from_protocol_schema(self):
        """Initialize database using protocol's schema.sql if available"""
        protocol_path = Path("protocols") / self.protocol_name
        schema_path = protocol_path / "schema.sql"
        
        if schema_path.exists():
            # Read and process the schema
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            # Remove INDEX statements from CREATE TABLE (SQLite doesn't support inline INDEX)
            # We'll create indexes separately
            lines = schema_sql.split('\n')
            cleaned_lines = []
            indexes_to_create = []
            in_create_table = False
            table_name = None
            
            for line in lines:
                stripped = line.strip()
                if stripped.upper().startswith('CREATE TABLE'):
                    in_create_table = True
                    # Extract table name
                    import re
                    match = re.search(r'CREATE TABLE IF NOT EXISTS (\w+)', line, re.IGNORECASE)
                    if match:
                        table_name = match.group(1)
                    cleaned_lines.append(line)
                elif in_create_table and stripped.upper().startswith('INDEX '):
                    # Convert inline INDEX to CREATE INDEX statement
                    # INDEX idx_messages_sender (sender) -> CREATE INDEX idx_messages_sender ON messages (sender)
                    parts = stripped.split()
                    if len(parts) >= 3 and table_name:
                        idx_name = parts[1]
                        # Find the column(s) in parentheses
                        start = stripped.find('(')
                        if start != -1:
                            columns = stripped[start:]
                            # Remove trailing comma if present
                            columns = columns.rstrip(',')
                            indexes_to_create.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} {columns};")
                    # Skip this line in the CREATE TABLE
                    continue
                elif in_create_table and stripped.startswith('--'):
                    # Skip comment lines but don't add them
                    continue
                elif in_create_table and (');' in stripped or stripped == ')'):  
                    in_create_table = False
                    # Remove trailing comma from previous line if needed
                    if cleaned_lines and cleaned_lines[-1].rstrip().endswith(','):
                        cleaned_lines[-1] = cleaned_lines[-1].rstrip()[:-1]
                    cleaned_lines.append(line)
                else:
                    cleaned_lines.append(line)
            
            cleaned_sql = '\n'.join(cleaned_lines)
            
            # Execute the cleaned schema
            cursor = self.conn.cursor()
            cursor.executescript(cleaned_sql)
            
            # Create indexes separately
            for idx_sql in indexes_to_create:
                try:
                    cursor.execute(idx_sql)
                except sqlite3.OperationalError:
                    # Ignore if index already exists
                    pass
            
            self.conn.commit()
            
            # Also create our generic tables for compatibility
            self._init_default_tables()
        else:
            # Fall back to default tables
            self._init_default_tables()
    
    def _init_default_tables(self):
        """Initialize default storage tables for dict compatibility"""
        cursor = self.conn.cursor()
        
        # Generic key-value store for state data that doesn't fit protocol schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        
        # Generic event store if protocol doesn't define one
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _event_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_data TEXT NOT NULL
            )
        """)
        
        # Generic list tables for any list-based data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _list_store (
                list_name TEXT NOT NULL,
                item_order INTEGER NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY (list_name, item_order)
            )
        """)
        
        self.conn.commit()
    
    def _load_cache(self):
        """Load all data into cache from the database"""
        cursor = self.conn.cursor()
        
        # Initialize cache - empty by default, populated from database
        self._cache = {}
        
        # Load all key-value data
        try:
            for row in cursor.execute("SELECT key, value FROM _kv_store"):
                key = row['key']
                value = json.loads(row['value'])
                self._cache[key] = value
        except sqlite3.OperationalError:
            pass
        
        # Load all list data
        try:
            list_data = {}
            for row in cursor.execute("SELECT list_name, item_order, data FROM _list_store ORDER BY list_name, item_order"):
                list_name = row['list_name']
                if list_name not in list_data:
                    list_data[list_name] = []
                list_data[list_name].append(json.loads(row['data']))
            
            # Add lists to cache
            for list_name, items in list_data.items():
                self._cache[list_name] = items
        except sqlite3.OperationalError:
            pass
        
        # Load event store if it exists
        try:
            events = []
            for row in cursor.execute("SELECT event_data FROM _event_store ORDER BY id"):
                events.append(json.loads(row['event_data']))
            if events:
                self._cache['eventStore'] = events
        except sqlite3.OperationalError:
            pass
    
    def __getitem__(self, key):
        """Get item from dict"""
        if key not in self._cache:
            raise KeyError(key)
        return self._cache[key]
    
    def __setitem__(self, key, value):
        """Set item in dict and persist"""
        self._cache[key] = value
        self._persist_key(key, value)
    
    def __delitem__(self, key):
        """Delete item from dict"""
        del self._cache[key]
        self._delete_key(key)
    
    def __iter__(self):
        """Iterate over keys"""
        return iter(self._cache)
    
    def __len__(self):
        """Return number of keys"""
        return len(self._cache)
    
    def __contains__(self, key):
        """Check if key exists"""
        return key in self._cache
    
    def _persist_key(self, key, value):
        """Persist a key to the database"""
        cursor = self.conn.cursor()
        
        if isinstance(value, dict):
            # For dict values, store as a single JSON blob in kv_store
            cursor.execute("""
                INSERT OR REPLACE INTO _kv_store (key, value)
                VALUES (?, ?)
            """, (key, json.dumps(value)))
        
        elif isinstance(value, list):
            # For list values, store in list_store with ordering
            # First delete existing entries for this list
            cursor.execute("DELETE FROM _list_store WHERE list_name = ?", (key,))
            
            # Then insert new entries with order preserved
            for idx, item in enumerate(value):
                cursor.execute("""
                    INSERT INTO _list_store (list_name, item_order, data)
                    VALUES (?, ?, ?)
                """, (key, idx, json.dumps(item)))
            
            # Special handling for eventStore to maintain compatibility
            if key == 'eventStore':
                cursor.execute("DELETE FROM _event_store")
                for event in value:
                    cursor.execute("""
                        INSERT INTO _event_store (event_data)
                        VALUES (?)
                    """, (json.dumps(event),))
        
        else:
            # For primitive values, store as JSON in kv_store
            cursor.execute("""
                INSERT OR REPLACE INTO _kv_store (key, value)
                VALUES (?, ?)
            """, (key, json.dumps(value)))
        
        self.conn.commit()
    
    def _delete_key(self, key):
        """Delete a key from the database"""
        cursor = self.conn.cursor()
        
        # Delete from kv_store
        cursor.execute("DELETE FROM _kv_store WHERE key = ?", (key,))
        
        # Delete from list_store if it's a list
        cursor.execute("DELETE FROM _list_store WHERE list_name = ?", (key,))
        
        # Special handling for eventStore
        if key == 'eventStore':
            cursor.execute("DELETE FROM _event_store")
        
        self.conn.commit()
    
    def clear(self):
        """Clear all data"""
        cursor = self.conn.cursor()
        
        # Clear only generic tables - protocol tables are managed by handlers
        cursor.execute("DELETE FROM _kv_store")
        cursor.execute("DELETE FROM _event_store")
        cursor.execute("DELETE FROM _list_store")
        
        self.conn.commit()
        self._cache.clear()
    
    def update(self, other):
        """Update dict with another dict"""
        for key, value in other.items():
            self[key] = value
    
    def to_dict(self):
        """Convert to plain dict for compatibility"""
        return dict(self._cache)
    
    def update_nested(self, key, updater_func):
        """
        Update a nested value and trigger persistence.
        
        Usage:
            db.update_nested('state', lambda s: s['items'].append(item))
        """
        value = self.get(key, {})
        updater_func(value)
        self[key] = value  # Trigger persistence
        return value
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None
    
    def __del__(self):
        """Ensure connection is closed when object is garbage collected"""
        self.close()

def create_db(db_path=None, protocol_name=None):
    """
    Create a persistent database instance.
    
    Args:
        db_path: Path to SQLite file. If None, uses in-memory database.
        protocol_name: Name of protocol to load schema from.
    
    Returns:
        PersistentDict instance that acts like a dict but persists to SQLite.
    """
    if db_path is None:
        # Use environment variable or in-memory
        db_path = os.environ.get('DB_PATH', ':memory:')
    
    # Detect protocol from environment if not provided
    if protocol_name is None and 'HANDLER_PATH' in os.environ:
        handler_path = Path(os.environ['HANDLER_PATH'])
        # Handler path is like protocols/message_via_tor/handlers
        # Get the protocol name from the path
        parts = handler_path.parts
        for i, part in enumerate(parts):
            if part == 'protocols' and i + 1 < len(parts):
                protocol_name = parts[i + 1]
                break
    
    return PersistentDict(db_path, protocol_name)