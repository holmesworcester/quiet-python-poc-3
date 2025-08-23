# Direct SQL Table Definitions in Handlers

This document explores defining SQL table structures directly in handler.json files, providing complete control over database schema including indexes, foreign keys, and table relationships.

## Overview

Instead of inferring schemas from tests or JSON Schema, handlers explicitly declare their SQL table requirements. This approach:
- Provides complete clarity about database structure
- Allows fine-grained control over indexes and constraints
- Makes foreign key relationships explicit
- Enables gradual migration from dict to SQL

## Handler SQL Definition Format

### Basic Structure

```json
{
  "type": "message",
  "tables": {
    "messages": {
      "columns": {
        "id": {
          "type": "INTEGER",
          "primary_key": true,
          "autoincrement": true
        },
        "event_id": {
          "type": "VARCHAR(64)",
          "unique": true,
          "nullable": false,
          "index": true
        },
        "text": {
          "type": "TEXT",
          "nullable": false
        },
        "sender_pubkey": {
          "type": "VARCHAR(64)",
          "nullable": false,
          "index": true
        },
        "reply_to_id": {
          "type": "INTEGER",
          "nullable": true
        },
        "created_at": {
          "type": "BIGINT",
          "nullable": false,
          "index": true
        },
        "signature": {
          "type": "VARCHAR(128)",
          "nullable": false
        }
      },
      "indexes": [
        {
          "name": "idx_messages_sender_time",
          "columns": ["sender_pubkey", "created_at"],
          "unique": false
        }
      ],
      "foreign_keys": [
        {
          "column": "sender_pubkey",
          "references": "identities.pubkey",
          "on_delete": "CASCADE"
        },
        {
          "column": "reply_to_id",
          "references": "messages.id",
          "on_delete": "SET NULL"
        }
      ]
    }
  },
  "table_access": {
    "reads": {
      "identities": ["pubkey", "name"],
      "messages": ["*"]  // for replyTo validation
    },
    "writes": {
      "messages": ["*"],
      "message_recipients": ["*"]  // for multi-recipient messages
    }
  }
}
```

### Advanced Example: Many-to-Many Relationships

```json
{
  "type": "group_message",
  "tables": {
    "group_messages": {
      "columns": {
        "id": {"type": "INTEGER", "primary_key": true},
        "event_id": {"type": "VARCHAR(64)", "unique": true},
        "group_id": {"type": "VARCHAR(64)", "nullable": false},
        "sender_pubkey": {"type": "VARCHAR(64)", "nullable": false},
        "content": {"type": "TEXT", "nullable": false},
        "created_at": {"type": "BIGINT", "nullable": false}
      }
    },
    "group_members": {
      "columns": {
        "group_id": {"type": "VARCHAR(64)", "nullable": false},
        "member_pubkey": {"type": "VARCHAR(64)", "nullable": false},
        "joined_at": {"type": "BIGINT", "nullable": false},
        "role": {"type": "VARCHAR(20)", "default": "'member'"}
      },
      "indexes": [
        {
          "name": "pk_group_members",
          "columns": ["group_id", "member_pubkey"],
          "primary": true
        }
      ],
      "foreign_keys": [
        {
          "column": "member_pubkey",
          "references": "identities.pubkey",
          "on_delete": "CASCADE"
        }
      ]
    }
  }
}
```

## SQL Type Mapping

### Standard SQL Types
```json
{
  "columns": {
    // Numeric types
    "count": {"type": "INTEGER"},
    "amount": {"type": "DECIMAL(10,2)"},
    "timestamp": {"type": "BIGINT"},
    
    // String types
    "pubkey": {"type": "VARCHAR(64)"},
    "name": {"type": "VARCHAR(255)"},
    "bio": {"type": "TEXT"},
    
    // Binary types
    "data": {"type": "BLOB"},
    "thumbnail": {"type": "VARBINARY(1024)"},
    
    // JSON type (for flexible data)
    "metadata": {"type": "JSON"},
    
    // Boolean
    "is_verified": {"type": "BOOLEAN", "default": false}
  }
}
```

### Database-Specific Types

For SQLAlchemy compatibility, we can use generic types that map appropriately:

```json
{
  "columns": {
    "data": {
      "type": "JSON",  // Maps to JSON in PostgreSQL, TEXT in SQLite
      "sql_type_overrides": {
        "postgresql": "JSONB",
        "mysql": "JSON",
        "sqlite": "TEXT"
      }
    }
  }
}
```

## Implementation

### Phase 1: Table Builder

```python
# utils/sql_table_builder.py
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Index, ForeignKey,
    Integer, String, Text, BigInteger, Boolean, JSON, DECIMAL
)
from typing import Dict, Any
import json

class SQLTableBuilder:
    # SQL type mapping
    TYPE_MAP = {
        'INTEGER': Integer,
        'BIGINT': BigInteger,
        'TEXT': Text,
        'BOOLEAN': Boolean,
        'JSON': JSON,
    }
    
    def __init__(self):
        self.metadata = MetaData()
        self.tables = {}
        self.table_definitions = {}
        
    def load_handler_tables(self, handler_path: str):
        """Load table definitions from a handler.json file."""
        with open(handler_path) as f:
            handler = json.load(f)
            
        if 'tables' not in handler:
            return
            
        handler_type = handler['type']
        
        for table_name, table_def in handler['tables'].items():
            self._create_table(table_name, table_def)
            
            # Store definition for foreign key resolution
            self.table_definitions[table_name] = table_def
            
    def _create_table(self, table_name: str, table_def: Dict):
        """Create a SQLAlchemy table from definition."""
        columns = []
        
        # Create columns
        for col_name, col_def in table_def['columns'].items():
            column = self._create_column(col_name, col_def)
            columns.append(column)
            
        # Create table
        table = Table(table_name, self.metadata, *columns)
        
        # Add indexes
        for index_def in table_def.get('indexes', []):
            self._create_index(table, index_def)
            
        self.tables[table_name] = table
        return table
        
    def _create_column(self, name: str, definition: Dict) -> Column:
        """Create a SQLAlchemy column from definition."""
        # Parse SQL type
        sql_type = definition['type']
        
        # Handle parameterized types like VARCHAR(64)
        if '(' in sql_type:
            base_type = sql_type.split('(')[0]
            param = int(sql_type.split('(')[1].rstrip(')'))
            
            if base_type == 'VARCHAR':
                col_type = String(param)
            elif base_type == 'DECIMAL':
                # Parse DECIMAL(10,2) format
                precision, scale = map(int, sql_type[8:-1].split(','))
                col_type = DECIMAL(precision, scale)
            elif base_type == 'VARBINARY':
                col_type = String(param)  # Simplified for example
        else:
            col_type = self.TYPE_MAP.get(sql_type, Text)
            
        # Build column arguments
        kwargs = {
            'nullable': definition.get('nullable', True),
            'unique': definition.get('unique', False),
            'index': definition.get('index', False),
            'primary_key': definition.get('primary_key', False),
        }
        
        if 'default' in definition:
            kwargs['default'] = definition['default']
            
        if 'autoincrement' in definition:
            kwargs['autoincrement'] = definition['autoincrement']
            
        return Column(name, col_type, **kwargs)
        
    def _create_index(self, table: Table, index_def: Dict):
        """Create an index on a table."""
        columns = [table.c[col_name] for col_name in index_def['columns']]
        
        if index_def.get('primary'):
            # Primary key constraint
            for col in columns:
                col.primary_key = True
        else:
            # Regular index
            Index(
                index_def['name'],
                *columns,
                unique=index_def.get('unique', False)
            )
            
    def resolve_foreign_keys(self):
        """Resolve foreign keys after all tables are created."""
        for table_name, table_def in self.table_definitions.items():
            table = self.tables[table_name]
            
            for fk_def in table_def.get('foreign_keys', []):
                # Parse reference like "identities.pubkey"
                ref_table, ref_column = fk_def['references'].split('.')
                
                # Add foreign key constraint
                col = table.c[fk_def['column']]
                col.append_foreign_key(
                    ForeignKey(
                        f"{ref_table}.{ref_column}",
                        ondelete=fk_def.get('on_delete', 'CASCADE')
                    )
                )
                
    def generate_create_sql(self, dialect='sqlite'):
        """Generate CREATE TABLE statements."""
        from sqlalchemy.schema import CreateTable
        
        statements = []
        for table in self.metadata.sorted_tables:
            create = CreateTable(table)
            statements.append(str(create.compile()))
            
        return '\n\n'.join(statements)
```

### Phase 2: Migration Bridge

```python
# utils/dict_to_sql_bridge.py
class DictToSQLBridge:
    """Bridge between dict-based storage and SQL tables."""
    
    def __init__(self, session, table_definitions):
        self.session = session
        self.table_definitions = table_definitions
        
    def migrate_handler_data(self, handler_type: str, dict_db: Dict):
        """Migrate data from dict storage to SQL tables."""
        handler_tables = self.table_definitions.get(handler_type, {})
        
        for table_name, table_def in handler_tables.items():
            if table_name == 'messages':
                self._migrate_messages(dict_db)
            elif table_name == 'identities':
                self._migrate_identities(dict_db)
            # ... other table migrations
            
    def _migrate_messages(self, dict_db: Dict):
        """Migrate messages from dict to SQL."""
        messages = dict_db.get('state', {}).get('messages', [])
        
        for msg in messages:
            # Transform dict structure to SQL row
            row = {
                'event_id': msg.get('eventId'),
                'text': msg.get('text'),
                'sender_pubkey': msg.get('sender'),
                'created_at': msg.get('timestamp'),
                'signature': msg.get('sig')
            }
            
            # Insert into SQL table
            self.session.execute(
                self.tables['messages'].insert().values(**row)
            )
            
        self.session.commit()
```

### Phase 3: Handler Integration

Handlers can work with both storage systems during migration:

```python
# handlers/message/projector.py
def project(db, envelope, time_now_ms, current_identity):
    """Project message event to database."""
    
    if hasattr(db, 'sql_session'):
        # SQL mode
        return project_to_sql(db, envelope, time_now_ms)
    else:
        # Dict mode
        return project_to_dict(db, envelope, time_now_ms)
        
def project_to_sql(db, envelope, time_now_ms):
    """Project to SQL tables."""
    data = envelope['data']
    
    # Insert into messages table
    message = db.tables['messages'].insert().values(
        event_id=envelope['metadata']['eventId'],
        text=data['text'],
        sender_pubkey=data['sender'],
        created_at=time_now_ms,
        signature=data['sig']
    )
    
    db.sql_session.execute(message)
    
    # Handle recipients if needed
    if 'recipients' in data:
        for recipient in data['recipients']:
            recipient_row = db.tables['message_recipients'].insert().values(
                message_event_id=envelope['metadata']['eventId'],
                recipient_pubkey=recipient
            )
            db.sql_session.execute(recipient_row)
            
    return db
```

## Benefits of Direct SQL Definitions

1. **Complete Control**: Define exactly what you need in the database
2. **Performance**: Proper indexes from day one
3. **Referential Integrity**: Foreign keys enforce data consistency
4. **Clear Migration Path**: SQL definitions guide the transition
5. **Database Agnostic**: SQLAlchemy handles dialect differences
6. **Type Safety**: SQL types are explicit and validated

## Example: Complete Message Handler

```json
{
  "type": "message",
  "version": 1,
  "tables": {
    "messages": {
      "columns": {
        "id": {
          "type": "INTEGER",
          "primary_key": true,
          "autoincrement": true
        },
        "event_id": {
          "type": "VARCHAR(64)",
          "unique": true,
          "nullable": false,
          "index": true
        },
        "conversation_id": {
          "type": "VARCHAR(64)",
          "nullable": true,
          "index": true,
          "comment": "Groups related messages"
        },
        "text": {
          "type": "TEXT",
          "nullable": false
        },
        "sender_pubkey": {
          "type": "VARCHAR(64)",
          "nullable": false,
          "index": true
        },
        "reply_to_id": {
          "type": "INTEGER",
          "nullable": true
        },
        "created_at": {
          "type": "BIGINT",
          "nullable": false,
          "index": true
        },
        "edited_at": {
          "type": "BIGINT",
          "nullable": true
        },
        "signature": {
          "type": "VARCHAR(128)",
          "nullable": false
        },
        "metadata": {
          "type": "JSON",
          "nullable": true,
          "comment": "Additional message properties"
        }
      },
      "indexes": [
        {
          "name": "idx_conversation_time",
          "columns": ["conversation_id", "created_at"]
        },
        {
          "name": "idx_sender_conversation",
          "columns": ["sender_pubkey", "conversation_id", "created_at"]
        }
      ],
      "foreign_keys": [
        {
          "column": "sender_pubkey",
          "references": "identities.pubkey",
          "on_delete": "CASCADE"
        },
        {
          "column": "reply_to_id",
          "references": "messages.id",
          "on_delete": "SET NULL"
        }
      ],
      "constraints": [
        {
          "type": "CHECK",
          "name": "chk_edited_after_created",
          "condition": "edited_at IS NULL OR edited_at >= created_at"
        }
      ]
    },
    "message_attachments": {
      "columns": {
        "id": {"type": "INTEGER", "primary_key": true},
        "message_id": {"type": "INTEGER", "nullable": false},
        "attachment_type": {"type": "VARCHAR(20)", "nullable": false},
        "url": {"type": "TEXT", "nullable": false},
        "metadata": {"type": "JSON"}
      },
      "indexes": [
        {
          "name": "idx_message_attachments",
          "columns": ["message_id"]
        }
      ],
      "foreign_keys": [
        {
          "column": "message_id",
          "references": "messages.id",
          "on_delete": "CASCADE"
        }
      ]
    }
  },
  "table_access": {
    "reads": {
      "identities": ["pubkey", "name", "blocked"],
      "messages": ["*"],
      "conversation_members": ["conversation_id", "member_pubkey"]
    },
    "writes": {
      "messages": ["*"],
      "message_attachments": ["*"],
      "message_events": ["*"]
    }
  },
  "dependencies": {
    "reads": ["identity", "conversation"],
    "writes_read_by": ["sync", "export", "search"]
  }
}
```

## Migration Strategy

1. **Add SQL definitions** to handlers incrementally
2. **Run table builder** to generate schema
3. **Implement bridge code** for dual operation
4. **Migrate data** table by table
5. **Switch to SQL mode** when ready
6. **Remove dict code** after validation

This approach provides maximum clarity and control while supporting gradual migration.