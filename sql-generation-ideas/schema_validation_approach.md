# SQL Schema vs Handler JSON Validation

## The Challenge

Validating that SQL schemas match handler JSON schemas involves comparing two very different representations:

### SQL Schema
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    event_id VARCHAR(64) UNIQUE NOT NULL,
    text TEXT NOT NULL,
    sender_pubkey VARCHAR(64) NOT NULL,
    metadata JSON
);
```

### Handler JSON Schema
```json
{
  "type": "object",
  "properties": {
    "type": {"const": "message"},
    "text": {"type": "string", "minLength": 1},
    "sender": {"type": "string"},
    "metadata": {"type": "object"}
  },
  "required": ["type", "text", "sender"]
}
```

## Why It's Non-Trivial

1. **Different Type Systems**
   - SQL: `VARCHAR(64)`, `TEXT`, `INTEGER`
   - JSON Schema: `string`, `number`, `object`
   - Need mapping between type systems

2. **Different Constraints**
   - SQL: `NOT NULL`, `UNIQUE`, `CHECK` constraints
   - JSON Schema: `required`, `minLength`, `pattern`
   - Not all constraints map cleanly

3. **Structural Differences**
   - SQL: Flat table structure
   - JSON: Nested objects, arrays
   - Events in handlers might map to multiple tables

4. **Naming Mismatches**
   - Handler field: `sender`
   - SQL column: `sender_pubkey`
   - Need a mapping system

## Practical Validation Approach

### 1. **Focus on What Matters**

Instead of perfect schema matching, validate the important things:

```python
# core/schema_validator.py
class SchemaValidator:
    def __init__(self, sql_schema_path):
        self.tables = self._load_sql_tables(sql_schema_path)
        self.warnings = []
        self.errors = []
    
    def validate_handler(self, handler_path):
        """Validate a handler's data access against SQL schema."""
        handler = json.load(open(handler_path))
        
        # Check projector test outputs
        if 'projector' in handler:
            self._validate_projector_tests(handler)
            
        # Check command outputs
        for cmd in handler.get('commands', {}).values():
            self._validate_command_tests(cmd)
            
    def _validate_projector_tests(self, handler):
        """Check that test outputs match SQL schema."""
        for test in handler['projector'].get('tests', []):
            then_db = test.get('then', {}).get('db', {})
            self._check_db_operations(then_db, handler['type'])
    
    def _check_db_operations(self, db_state, handler_type):
        """Validate database operations against schema."""
        # Check state modifications
        for key, value in db_state.get('state', {}).items():
            if key == 'messages' and isinstance(value, list):
                for msg in value:
                    self._validate_message_fields(msg)
            elif key == 'identities' and isinstance(value, list):
                for identity in value:
                    self._validate_identity_fields(identity)
                    
    def _validate_message_fields(self, message):
        """Check message fields against SQL schema."""
        # Required SQL columns
        sql_required = ['text', 'sender_pubkey', 'signature']
        
        # Map handler fields to SQL columns
        field_map = {
            'sender': 'sender_pubkey',
            'sig': 'signature'
        }
        
        for sql_col in sql_required:
            handler_field = next(
                (k for k, v in field_map.items() if v == sql_col), 
                sql_col
            )
            
            if handler_field not in message:
                self.errors.append(
                    f"Missing required field '{handler_field}' "
                    f"(SQL column: {sql_col})"
                )
```

### 2. **Simple Mapping File**

Create a mapping between handler fields and SQL columns:

```yaml
# schema/field_mappings.yaml
mappings:
  message:
    handler_to_sql:
      sender: sender_pubkey
      sig: signature
      timestamp: created_at
    sql_to_handler:
      sender_pubkey: sender
      signature: sig
      created_at: timestamp
    
  identity:
    handler_to_sql:
      pubkey: pubkey
      name: name
```

### 3. **Validation Rules File**

Define what needs to be validated:

```yaml
# schema/validation_rules.yaml
rules:
  messages:
    required_fields:
      - text
      - sender_pubkey
      - signature
    field_types:
      text: string
      sender_pubkey: string[64]  # string with length
      created_at: integer
    constraints:
      sender_pubkey: 
        must_exist_in: identities.pubkey
        
  identities:
    required_fields:
      - pubkey
      - name
    unique_fields:
      - pubkey
```

### 4. **Practical Test Runner Integration**

```python
def run_handler_test(test, handler):
    """Run test and validate against SQL schema."""
    # Run the test normally
    result = execute_test(test, handler)
    
    # If test passed, validate schema compliance
    if result.passed:
        validator = SchemaValidator()
        schema_issues = validator.validate_test_output(
            test, 
            handler['type']
        )
        
        if schema_issues:
            result.add_warnings(schema_issues)
            
    return result
```

## What to Actually Validate

### High Priority (Errors)
1. **Required fields missing** - Fields marked NOT NULL in SQL
2. **Type mismatches** - String in JSON, INTEGER in SQL
3. **Foreign key violations** - Reference to non-existent record
4. **Unique violations** - Duplicate values in unique columns

### Medium Priority (Warnings)
1. **Field not in SQL** - Handler uses field not in schema
2. **Length violations** - String exceeds VARCHAR length
3. **Missing indexes** - Querying on non-indexed fields

### Low Priority (Info)
1. **Unused SQL columns** - Schema has columns handlers don't use
2. **Type coercion** - Automatic type conversions

## Implementation Strategy

```python
# Simple validation that's actually useful
class PracticalValidator:
    def __init__(self):
        # Parse SQL schema once
        self.tables = parse_sql_file("schema/tables.sql")
        
        # Load mappings
        self.mappings = load_yaml("schema/field_mappings.yaml")
        
    def check_handler_output(self, handler_type, output_data):
        """Basic sanity checks."""
        issues = []
        
        # Get expected table for this handler
        table = self.get_table_for_handler(handler_type)
        if not table:
            return ["No table found for handler type"]
            
        # Check required fields
        for field in table.required_fields:
            mapped_field = self.map_sql_to_handler(field, handler_type)
            if mapped_field not in output_data:
                issues.append(f"Missing required: {mapped_field}")
                
        return issues
```

## Recommendation

1. **Don't aim for perfect validation** - It's too complex
2. **Focus on catching real errors** - Missing required fields, type issues
3. **Use simple mapping files** - Document field name differences
4. **Validate at test time** - Catch issues early
5. **Make it informative** - Clear error messages

The goal is to catch the most common mistakes (missing required fields, wrong types) without building a full SQL parser and type system.