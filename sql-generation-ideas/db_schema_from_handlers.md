# Database Schema Extraction from Handler Schemas and Tests

This document describes how to automatically derive database schemas from handler definitions and test patterns, enabling a smooth transition from dict-based storage to SQLAlchemy.

## Overview

We extract database schemas by analyzing:
1. **Formal schemas** from projector and command output definitions (primary source)
2. **Write patterns** from projector test outputs (`then` blocks) to validate and enhance
4. **Data shapes** from both schemas and actual test data

This dual approach ensures complete coverage even if tests are incomplete, while tests validate that schemas match actual usage.

## Current Dict-Based System

### Phase 1: Add Handler Dependencies and Schemas

First, enhance your handler.json files with:

1. **Dependencies** to track data flow between handlers:
```json
{
  "type": "message",
  "dependencies": {
    "reads": ["identity"],           // Handlers whose data we read
    "optional_reads": ["message"],   // For features like replyTo
    "writes_read_by": ["sync_peers"] // Handlers that read our data
  }
}
```

2. **Formal output schemas** for projectors and commands:
```json
{
  "type": "message",
  "schema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "type": {"const": "message"},
      "text": {"type": "string", "minLength": 1},
      "sender": {"type": "string"},
      "signature": {"type": "string"},
      "replyTo": {"type": "string"}
    },
    "required": ["type", "text", "sender", "signature"]
  },
  "projector": {
    "outputSchema": {
      "type": "object",
      "properties": {
        "db": {
          "type": "object",
          "properties": {
            "state": {
              "type": "object",
              "properties": {
                "messages": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "text": {"type": "string"},
                      "sender": {"type": "string"},
                      "timestamp": {"type": "integer"}
                    }
                  }
                },
                "outgoing": {
                  "type": "array",
                  "items": {"type": "string"}
                }
              }
            },
            "eventStore": {
              "type": "object",
              "additionalProperties": {
                "type": "array",
                "items": {"$ref": "#/definitions/event"}
              }
            }
          }
        }
      }
    },
    "tests": [ /* existing tests validate the schema */ ]
  },
  "commands": {
    "create": {
      "outputSchema": {
        "type": "object",
        "properties": {
          "return": {"type": "string"},
          "newEvents": {
            "type": "array",
            "items": {"$ref": "#/schema"}
          }
        }
      }
    }
  }
}
```

### Phase 2: Enhanced Schema Extraction Tool

Create `utils/extract_schemas.py`:

```python
import json
import os
from typing import Dict, Set, Any, List
from collections import defaultdict

class SchemaExtractor:
    def __init__(self):
        self.formal_schemas = {}
        self.write_patterns = defaultdict(lambda: defaultdict(set))
        self.read_patterns = defaultdict(lambda: defaultdict(set))
        self.data_shapes = defaultdict(dict)
        
    def extract_from_handler(self, handler_path: str) -> Dict:
        """Extract schema patterns from a single handler."""
        with open(handler_path) as f:
            handler = json.load(f)
            
        handler_type = handler['type']
        
        # FIRST: Extract formal schemas from handler definitions
        self._extract_formal_schemas(handler_type, handler)
        
        # THEN: Validate and enhance with test patterns
        if 'projector' in handler and 'tests' in handler['projector']:
            for test in handler['projector']['tests']:
                self._analyze_writes(handler_type, test)
                self._analyze_reads(handler_type, test)
                
        # Extract from command tests
        for command_name, command in handler.get('commands', {}).items():
            # Extract formal command output schema
            if 'outputSchema' in command:
                self._record_formal_schema(handler_type, f"command.{command_name}.output", 
                                         command['outputSchema'])
            
            # Validate with tests
            for test in command.get('tests', []):
                self._analyze_command_output(handler_type, command_name, test)
                
        return {
            'type': handler_type,
            'formal_schemas': self.formal_schemas.get(handler_type, {}),
            'writes': dict(self.write_patterns[handler_type]),
            'reads': dict(self.read_patterns[handler_type]),
            'shapes': self.data_shapes[handler_type]
        }
    
    def _extract_formal_schemas(self, handler_type: str, handler: Dict):
        """Extract formally defined schemas from handler."""
        
        # Extract event schema if defined
        if 'schema' in handler:
            self._record_formal_schema(handler_type, 'event', handler['schema'])
            
        # Extract projector output schema if defined
        if 'projector' in handler and 'outputSchema' in handler['projector']:
            self._record_formal_schema(handler_type, 'projector.output', 
                                     handler['projector']['outputSchema'])
            
        # Extract command schemas
        for cmd_name, cmd_def in handler.get('commands', {}).items():
            if 'inputSchema' in cmd_def:
                self._record_formal_schema(handler_type, f'command.{cmd_name}.input', 
                                         cmd_def['inputSchema'])
            if 'outputSchema' in cmd_def:
                self._record_formal_schema(handler_type, f'command.{cmd_name}.output', 
                                         cmd_def['outputSchema'])
    
    def _record_formal_schema(self, handler_type: str, schema_path: str, schema: Dict):
        """Record a formal schema definition."""
        if handler_type not in self.formal_schemas:
            self.formal_schemas[handler_type] = {}
            
        self.formal_schemas[handler_type][schema_path] = schema
        
        # Also infer database paths from schema
        self._infer_db_paths_from_schema(handler_type, schema, schema_path)
    
    def _infer_db_paths_from_schema(self, handler_type: str, schema: Dict, context: str):
        """Infer database write paths from a JSON schema."""
        if schema.get('type') == 'object' and 'properties' in schema:
            # Check for db property in output schemas
            if 'db' in schema['properties']:
                db_schema = schema['properties']['db']
                if 'properties' in db_schema:
                    self._extract_db_paths_from_schema(handler_type, db_schema['properties'])
            
            # Check for direct state modifications
            elif 'state' in schema['properties']:
                state_schema = schema['properties']['state']
                if 'properties' in state_schema:
                    self._extract_db_paths_from_schema(handler_type, 
                                                     state_schema['properties'], 
                                                     'state')
            
            # Check for new events in command outputs
            for event_key in ['newEvents', 'new_events', 'newlyCreatedEvents']:
                if event_key in schema['properties']:
                    event_schema = schema['properties'][event_key]
                    if event_schema.get('type') == 'array' and 'items' in event_schema:
                        self._record_formal_schema(handler_type, 
                                                 f'{context}.{event_key}', 
                                                 event_schema['items'])
    
    def _extract_db_paths_from_schema(self, handler_type: str, properties: Dict, 
                                    prefix: str = ''):
        """Extract database paths from schema properties."""
        for key, prop_schema in properties.items():
            path = f"{prefix}.{key}" if prefix else key
            
            # Record this as a write path
            self.write_patterns[handler_type][path].add('schema')
            
            # Record the expected shape from schema
            if 'type' in prop_schema:
                self._record_shape_from_schema(handler_type, path, prop_schema)
            
            # Recurse for nested objects
            if prop_schema.get('type') == 'object' and 'properties' in prop_schema:
                self._extract_db_paths_from_schema(handler_type, 
                                                 prop_schema['properties'], 
                                                 path)
    
    def _record_shape_from_schema(self, handler_type: str, path: str, schema: Dict):
        """Record expected shape from a JSON schema."""
        if path not in self.data_shapes[handler_type]:
            self.data_shapes[handler_type][path] = {
                'schema': schema,
                'samples': [],
                'types': set()
            }
        else:
            self.data_shapes[handler_type][path]['schema'] = schema
    
    def _analyze_writes(self, handler_type: str, test: Dict):
        """Analyze what a test writes to the database."""
        given_db = test.get('given', {}).get('db', {})
        then_db = test.get('then', {}).get('db', {})
        
        # Compare given vs then to find modifications
        self._compare_db_states(handler_type, given_db, then_db, 'write')
        
    def _analyze_reads(self, handler_type: str, test: Dict):
        """Analyze what a test reads from the database."""
        given_db = test.get('given', {}).get('db', {})
        
        # Track all paths accessed in given
        self._extract_paths(handler_type, given_db, 'read')
        
    def _compare_db_states(self, handler_type: str, before: Dict, after: Dict, 
                          access_type: str, path: str = ''):
        """Compare two database states to find changes."""
        # Handle additions
        for key in after:
            current_path = f"{path}.{key}" if path else key
            
            if key not in before:
                # New key added
                self._record_access(handler_type, current_path, access_type)
                self._record_shape(handler_type, current_path, after[key])
            elif before[key] != after[key]:
                # Value changed
                self._record_access(handler_type, current_path, access_type)
                self._record_shape(handler_type, current_path, after[key])
                
                # Recurse for nested changes
                if isinstance(after[key], dict) and isinstance(before[key], dict):
                    self._compare_db_states(handler_type, before[key], 
                                          after[key], access_type, current_path)
                    
        # Handle deletions
        for key in before:
            if key not in after:
                current_path = f"{path}.{key}" if path else key
                self._record_access(handler_type, current_path, 'delete')
    
    def _extract_paths(self, handler_type: str, data: Any, access_type: str, 
                      path: str = ''):
        """Extract all paths from a data structure."""
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                self._record_access(handler_type, current_path, access_type)
                self._extract_paths(handler_type, value, access_type, current_path)
        elif isinstance(data, list) and data:
            # Record array access
            self._record_access(handler_type, f"{path}[]", access_type)
            # Sample first item for shape
            if data:
                self._record_shape(handler_type, f"{path}[]", data[0])
    
    def _record_access(self, handler_type: str, path: str, access_type: str):
        """Record that a handler accesses a path."""
        if access_type == 'write':
            self.write_patterns[handler_type][path].add('write')
        elif access_type == 'read':
            self.read_patterns[handler_type][path].add('read')
            
    def _record_shape(self, handler_type: str, path: str, sample_data: Any):
        """Record the shape of data at a path."""
        if path not in self.data_shapes[handler_type]:
            self.data_shapes[handler_type][path] = {
                'samples': [],
                'types': set()
            }
        
        self.data_shapes[handler_type][path]['samples'].append(sample_data)
        self.data_shapes[handler_type][path]['types'].add(type(sample_data).__name__)
    
    def _analyze_command_output(self, handler_type: str, command: str, test: Dict):
        """Analyze command outputs for new events."""
        then_return = test.get('then', {}).get('return', {})
        
        # Check for new events
        for event_list in ['newEvents', 'new_events', 'newlyCreatedEvents']:
            if event_list in then_return:
                for event in then_return[event_list]:
                    # Record event shape
                    self._record_shape(handler_type, f"events.{handler_type}", event)

def extract_all_schemas(handlers_dir: str) -> Dict:
    """Extract schemas from all handlers."""
    all_schemas = {}
    
    for root, dirs, files in os.walk(handlers_dir):
        if 'handler.json' in files:
            extractor = SchemaExtractor()
            schema = extractor.extract_from_handler(os.path.join(root, 'handler.json'))
            all_schemas[schema['type']] = schema
            
    return all_schemas

def generate_schema_report(schemas: Dict) -> str:
    """Generate a human-readable schema report."""
    report = ["# Extracted Database Schemas\n"]
    
    for handler_type, schema in schemas.items():
        report.append(f"\n## Handler: {handler_type}")
        
        # Show formal schemas first
        if 'formal_schemas' in schema and schema['formal_schemas']:
            report.append("\n### Formal Schemas:")
            for schema_path, formal_schema in schema['formal_schemas'].items():
                report.append(f"- `{schema_path}`: {formal_schema.get('type', 'unknown')}")
                if 'properties' in formal_schema:
                    props = ', '.join(formal_schema['properties'].keys())
                    report.append(f"  Properties: {props}")
        
        if schema['writes']:
            report.append("\n### Writes to:")
            for path in sorted(schema['writes'].keys()):
                sources = ', '.join(schema['writes'][path])
                report.append(f"- `{path}` (from: {sources})")
                
        if schema['reads']:
            report.append("\n### Reads from:")
            for path in sorted(schema['reads'].keys()):
                report.append(f"- `{path}`")
                
        if schema['shapes']:
            report.append("\n### Data Shapes:")
            for path, shape_info in schema['shapes'].items():
                if 'schema' in shape_info:
                    # Show formal schema type
                    schema_type = shape_info['schema'].get('type', 'unknown')
                    report.append(f"- `{path}`: {schema_type} (from schema)")
                elif shape_info['types']:
                    # Show inferred types from samples
                    types = ', '.join(shape_info['types'])
                    report.append(f"- `{path}`: {types} (from tests)")
                
    return '\n'.join(report)
```

### Phase 3: Run Schema Extraction

Create a script to analyze your handlers:

```python
# extract_and_report.py
from utils.extract_schemas import extract_all_schemas, generate_schema_report

# Extract schemas
schemas = extract_all_schemas('handlers/')

# Generate report
report = generate_schema_report(schemas)
print(report)

# Save for next phase
with open('extracted_schemas.json', 'w') as f:
    json.dump(schemas, f, indent=2)
```

## Transition to SQLAlchemy

### Phase 4: Schema to SQLAlchemy Mapper

Create `utils/schema_to_sqlalchemy.py`:

```python
from sqlalchemy import create_engine, Column, String, Integer, Text, JSON, ForeignKey, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from typing import Dict, Any
import json

Base = declarative_base()

class SchemaMapper:
    def __init__(self, extracted_schemas: Dict):
        self.schemas = extracted_schemas
        self.tables = {}
        self.metadata = MetaData()
        
    def generate_tables(self) -> Dict[str, Table]:
        """Generate SQLAlchemy tables from extracted schemas."""
        
        # First pass: identify all table needs
        table_definitions = self._identify_tables()
        
        # Second pass: create tables
        for table_name, columns in table_definitions.items():
            self.tables[table_name] = Table(
                table_name,
                self.metadata,
                *self._create_columns(table_name, columns)
            )
            
        return self.tables
    
    def _identify_tables(self) -> Dict[str, Dict]:
        """Identify tables from access patterns."""
        tables = defaultdict(dict)
        
        for handler_type, schema in self.schemas.items():
            for path in schema['writes']:
                table_name, column_path = self._path_to_table_column(path)
                if table_name:
                    # Infer column type from samples
                    column_type = self._infer_column_type(
                        schema['shapes'].get(path, {})
                    )
                    tables[table_name][column_path] = column_type
                    
        return tables
    
    def _path_to_table_column(self, path: str) -> tuple[str, str]:
        """Convert a path like 'state.messages[]' to ('messages', 'data')."""
        parts = path.split('.')
        
        if len(parts) >= 2 and parts[0] in ['state', 'eventStore']:
            # Remove state/eventStore prefix
            table_path = parts[1:]
            
            # Handle array notation
            if table_path[-1].endswith('[]'):
                table_name = table_path[-1][:-2]
                return (table_name, 'data')
            elif len(table_path) == 1:
                # Simple table
                return (table_path[0], 'data')
            else:
                # Nested path becomes column
                table_name = table_path[0]
                column_name = '_'.join(table_path[1:])
                return (table_name, column_name)
                
        return (None, None)
    
    def _infer_column_type(self, shape_info: Dict) -> type:
        """Infer SQLAlchemy column type from shape samples."""
        if not shape_info or not shape_info.get('samples'):
            return JSON  # Default to JSON for unknown types
            
        # Check first sample
        sample = shape_info['samples'][0]
        
        if isinstance(sample, str):
            # Check if it looks like an ID or hash
            if len(sample) == 64:  # Likely a hash
                return String(64)
            elif len(sample) < 255:
                return String(255)
            else:
                return Text
        elif isinstance(sample, int):
            return Integer
        elif isinstance(sample, dict) or isinstance(sample, list):
            return JSON
        else:
            return JSON
    
    def _create_columns(self, table_name: str, column_defs: Dict) -> list:
        """Create SQLAlchemy columns for a table."""
        columns = [
            Column('id', Integer, primary_key=True, autoincrement=True)
        ]
        
        # Add extracted columns
        for column_name, column_type in column_defs.items():
            columns.append(Column(column_name, column_type))
            
        # Add standard columns
        if table_name in ['messages', 'events']:
            columns.extend([
                Column('event_id', String(64), unique=True, index=True),
                Column('created_at', Integer),
                Column('sender', String(64), index=True)
            ])
            
        return columns

def generate_models_file(tables: Dict[str, Table]) -> str:
    """Generate a models.py file from tables."""
    code = [
        "# Auto-generated from handler tests",
        "from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey",
        "from sqlalchemy.ext.declarative import declarative_base",
        "",
        "Base = declarative_base()",
        ""
    ]
    
    for table_name, table in tables.items():
        class_name = ''.join(word.capitalize() for word in table_name.split('_'))
        code.append(f"class {class_name}(Base):")
        code.append(f"    __tablename__ = '{table_name}'")
        code.append("")
        
        for column in table.columns:
            col_def = f"    {column.name} = Column({column.type.__class__.__name__}"
            if column.primary_key:
                col_def += ", primary_key=True"
            if column.unique:
                col_def += ", unique=True"
            if column.index:
                col_def += ", index=True"
            col_def += ")"
            code.append(col_def)
        code.append("")
        
    return '\n'.join(code)
```

### Phase 5: Gradual Migration

Create `utils/db_adapter.py` to support both dict and SQLAlchemy:

```python
class DatabaseAdapter:
    """Adapter that supports both dict-based and SQLAlchemy databases."""
    
    def __init__(self, use_sqlalchemy=False, session=None):
        self.use_sqlalchemy = use_sqlalchemy
        self.session = session
        self.dict_db = {} if not use_sqlalchemy else None
        
    def get_state(self, path: str, default=None):
        """Get a value from state using path notation."""
        if self.use_sqlalchemy:
            return self._get_sqlalchemy(path, default)
        else:
            return self._get_dict(path, default)
            
    def set_state(self, path: str, value: Any):
        """Set a value in state using path notation."""
        if self.use_sqlalchemy:
            self._set_sqlalchemy(path, value)
        else:
            self._set_dict(path, value)
            
    def _get_dict(self, path: str, default=None):
        """Get from dict database."""
        parts = path.split('.')
        current = self.dict_db
        
        for part in parts:
            if part.endswith('[]'):
                # Array access
                key = part[:-2]
                current = current.get(key, [])
            else:
                current = current.get(part, {})
                
        return current if current else default
        
    def _set_dict(self, path: str, value: Any):
        """Set in dict database."""
        parts = path.split('.')
        current = self.dict_db
        
        # Navigate to parent
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            
        # Set final value
        final_key = parts[-1]
        if final_key.endswith('[]'):
            # Array append
            key = final_key[:-2]
            if key not in current:
                current[key] = []
            current[key].append(value)
        else:
            current[final_key] = value
            
    def _get_sqlalchemy(self, path: str, default=None):
        """Get from SQLAlchemy database."""
        # Implementation depends on your model structure
        # This is a simplified example
        table_name, column_path = self._parse_path(path)
        model_class = self._get_model_class(table_name)
        
        if model_class:
            results = self.session.query(model_class).all()
            # Process results based on column_path
            return results
        return default
        
    def _set_sqlalchemy(self, path: str, value: Any):
        """Set in SQLAlchemy database."""
        table_name, column_path = self._parse_path(path)
        model_class = self._get_model_class(table_name)
        
        if model_class:
            # Create or update record
            instance = model_class(**value)
            self.session.add(instance)
            self.session.commit()
```

### Phase 6: Migration Steps

1. **Run schema extraction** regularly as you develop
2. **Generate SQLAlchemy models** from extracted schemas
3. **Update handlers** to use DatabaseAdapter
4. **Test with both backends** using a feature flag
5. **Migrate data** from dicts to tables
6. **Switch to SQLAlchemy** when ready

## Best Practices

### 1. Keep Tests as Source of Truth
- Never manually edit generated schemas
- Update tests when data needs change
- Re-run extraction after test changes

### 2. Handler Dependencies
```json
{
  "dependencies": {
    "reads": ["identity", "peer"],
    "optional_reads": ["message"],
    "writes_read_by": ["sync_peers", "export"]
  }
}
```

### 3. Progressive Enhancement
- Start with basic extraction
- Add type inference as needed
- Refine table relationships over time

### 4. Validation
- Compare extracted schemas between runs
- Alert on unexpected changes
- Version your schema files

## Example Output

Running extraction on your handlers might produce:

```
# Extracted Database Schemas

## Handler: message

### Formal Schemas:
- `event`: object
  Properties: type, text, sender, signature, replyTo
- `projector.output`: object
  Properties: db
- `command.create.output`: object
  Properties: return, newEvents

### Writes to:
- `state.messages[]` (from: schema, write)
- `state.outgoing[]` (from: schema, write)
- `eventStore.{sender}[]` (from: write)

### Reads from:
- `state.known_senders[]`
- `state.key_map`

### Data Shapes:
- `state.messages[]`: array (from schema)
- `events.message`: object (from schema)
  Properties: type, text, sender, signature

## Handler: identity

### Formal Schemas:
- `event`: object
  Properties: type, pubkey, name

### Writes to:
- `state.identities[]` (from: write)
- `state.known_senders[]` (from: write)
- `state.peers[]` (from: write)

### Reads from:
- `state.identities[]`
```

This schema can then generate:

```python
class Messages(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    event_id = Column(String(64), unique=True, index=True)
    text = Column(Text)
    sender = Column(String(64), index=True)
    signature = Column(String(128))
    created_at = Column(Integer)
```

## Benefits of the Combined Approach

Using both formal schemas and test extraction provides:

1. **Complete Coverage**: Formal schemas ensure nothing is missed even if tests are incomplete
2. **Validation**: Tests validate that schemas match actual usage
3. **Type Safety**: JSON Schema provides strong typing for SQLAlchemy generation
4. **Documentation**: Schemas serve as API contracts between handlers
5. **Early Detection**: Schema violations caught during testing, not production
6. **Gradual Migration**: Can add schemas incrementally as you transition

## Conclusion

This approach ensures:
- **Formal schemas define the contract** (what SHOULD happen)
- **Tests validate the implementation** (what DOES happen)
- **Extraction tools bridge to SQLAlchemy** (automated migration)
- **No manual schema maintenance** after initial setup
- **Type safety emerges from both schemas and usage**
- **Dependencies explicitly document data flow**

The database schema evolves naturally with your application, with formal schemas providing the structure and tests ensuring correctness.