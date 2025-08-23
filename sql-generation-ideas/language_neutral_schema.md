# Language-Neutral SQL Schema Definition Options

## 1. **Raw SQL Files** (Most Universal)

The most language-neutral approach is plain SQL DDL statements:

```sql
-- schema/tables.sql
CREATE TABLE IF NOT EXISTS identities (
    pubkey VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    metadata JSON
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id VARCHAR(64) UNIQUE NOT NULL,
    sender_pubkey VARCHAR(64) NOT NULL,
    text TEXT NOT NULL,
    reply_to_id INTEGER,
    created_at BIGINT NOT NULL,
    signature VARCHAR(128) NOT NULL,
    FOREIGN KEY (sender_pubkey) REFERENCES identities(pubkey) ON DELETE CASCADE,
    FOREIGN KEY (reply_to_id) REFERENCES messages(id) ON DELETE SET NULL
);

CREATE INDEX idx_messages_sender ON messages(sender_pubkey);
CREATE INDEX idx_messages_created ON messages(created_at);
CREATE INDEX idx_messages_sender_time ON messages(sender_pubkey, created_at);
```

**Pros:**
- Works with any database and programming language
- Can be executed directly by database tools
- Version control friendly
- No parsing needed

**Cons:**
- Database-specific syntax differences (though core DDL is quite standard)
- No programmatic access without SQL parsing

## 2. **JSON Schema with SQL Extensions**

A structured JSON format that can be parsed by any language:

```json
{
  "version": "1.0",
  "tables": {
    "identities": {
      "columns": [
        {"name": "pubkey", "type": "VARCHAR", "length": 64, "primary_key": true},
        {"name": "name", "type": "VARCHAR", "length": 255, "nullable": false},
        {"name": "created_at", "type": "BIGINT", "nullable": false},
        {"name": "updated_at", "type": "BIGINT", "nullable": false},
        {"name": "metadata", "type": "JSON", "nullable": true}
      ]
    },
    "messages": {
      "columns": [
        {"name": "id", "type": "INTEGER", "primary_key": true, "autoincrement": true},
        {"name": "event_id", "type": "VARCHAR", "length": 64, "unique": true, "nullable": false},
        {"name": "sender_pubkey", "type": "VARCHAR", "length": 64, "nullable": false},
        {"name": "text", "type": "TEXT", "nullable": false},
        {"name": "reply_to_id", "type": "INTEGER", "nullable": true},
        {"name": "created_at", "type": "BIGINT", "nullable": false},
        {"name": "signature", "type": "VARCHAR", "length": 128, "nullable": false}
      ],
      "foreign_keys": [
        {
          "column": "sender_pubkey",
          "references": {"table": "identities", "column": "pubkey"},
          "on_delete": "CASCADE"
        },
        {
          "column": "reply_to_id",
          "references": {"table": "messages", "column": "id"},
          "on_delete": "SET NULL"
        }
      ],
      "indexes": [
        {"name": "idx_messages_sender", "columns": ["sender_pubkey"]},
        {"name": "idx_messages_created", "columns": ["created_at"]},
        {"name": "idx_messages_sender_time", "columns": ["sender_pubkey", "created_at"]}
      ]
    }
  }
}
```

**Pros:**
- Parseable by any language
- Structured and validatable
- Can generate SQL for different databases

**Cons:**
- Requires implementation in each language
- Another abstraction layer

## 3. **YAML Schema Definition**

More human-readable than JSON:

```yaml
# schema/database.yaml
version: 1.0
tables:
  identities:
    columns:
      - name: pubkey
        type: VARCHAR(64)
        primary_key: true
      - name: name
        type: VARCHAR(255)
        nullable: false
      - name: created_at
        type: BIGINT
        nullable: false
      - name: updated_at
        type: BIGINT
        nullable: false
      - name: metadata
        type: JSON
        
  messages:
    columns:
      - name: id
        type: INTEGER
        primary_key: true
        autoincrement: true
      - name: event_id
        type: VARCHAR(64)
        unique: true
        nullable: false
      - name: sender_pubkey
        type: VARCHAR(64)
        nullable: false
      - name: text
        type: TEXT
        nullable: false
      - name: reply_to_id
        type: INTEGER
        nullable: true
      - name: created_at
        type: BIGINT
        nullable: false
      - name: signature
        type: VARCHAR(128)
        nullable: false
    
    foreign_keys:
      - column: sender_pubkey
        references: identities.pubkey
        on_delete: CASCADE
      - column: reply_to_id
        references: messages.id
        on_delete: SET NULL
        
    indexes:
      - name: idx_messages_sender
        columns: [sender_pubkey]
      - name: idx_messages_created
        columns: [created_at]
      - name: idx_messages_sender_time
        columns: [sender_pubkey, created_at]
```

**Pros:**
- Very readable
- Comments support
- Widely supported

**Cons:**
- YAML parsers vary slightly between languages
- Indentation sensitive

## 4. **SQL Migration Files** (Recommended)

Combine versioned SQL files with a simple manifest:

```
schema/
├── manifest.json
├── 001_initial_tables.sql
├── 002_add_indexes.sql
├── 003_add_message_attachments.sql
└── 004_add_conversation_support.sql
```

**manifest.json:**
```json
{
  "version": 4,
  "migrations": [
    {"version": 1, "file": "001_initial_tables.sql", "description": "Initial tables"},
    {"version": 2, "file": "002_add_indexes.sql", "description": "Performance indexes"},
    {"version": 3, "file": "003_add_message_attachments.sql", "description": "Attachment support"},
    {"version": 4, "file": "004_add_conversation_support.sql", "description": "Conversation threading"}
  ]
}
```

**001_initial_tables.sql:**
```sql
-- Create identities table
CREATE TABLE IF NOT EXISTS identities (
    pubkey VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL
);

-- Create messages table
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id VARCHAR(64) UNIQUE NOT NULL,
    sender_pubkey VARCHAR(64) NOT NULL,
    text TEXT NOT NULL,
    created_at BIGINT NOT NULL,
    signature VARCHAR(128) NOT NULL,
    FOREIGN KEY (sender_pubkey) REFERENCES identities(pubkey) ON DELETE CASCADE
);
```

**Pros:**
- Versioning built-in
- Can be applied by any SQL tool
- Clear migration path
- Language agnostic

**Cons:**
- Need to track applied migrations

## 5. **Hybrid Approach** (Best of Both)

Use SQL files as source of truth with a JSON/YAML manifest for tooling:

**schema/manifest.yaml:**
```yaml
version: 1.0
dialect: sqlite  # or postgresql, mysql
tables:
  - name: identities
    file: tables/identities.sql
    description: User identity records
  - name: messages
    file: tables/messages.sql
    description: Message events
  - name: message_attachments
    file: tables/message_attachments.sql
    description: File attachments for messages

indexes:
  - file: indexes/performance.sql
    description: Performance optimization indexes

views:
  - file: views/conversation_threads.sql
    description: Conversation threading views
```

Then each SQL file contains standard DDL.

## Recommendation

For maximum language neutrality and simplicity, I recommend:

1. **Primary**: Raw SQL files in a `schema/` directory
2. **Manifest**: Simple JSON/YAML listing the files and their order
3. **Validation**: Test runner reads the SQL files and validates handler access

This approach:
- Works with any language that can read files
- Uses SQL as the universal database language
- Requires no special parsers
- Can be applied manually or programmatically
- Supports gradual evolution through migrations

Example structure:
```
protocol/
├── schema/
│   ├── setup.sql          # Main schema file
│   ├── indexes.sql        # Performance indexes
│   ├── migrations/        # Future changes
│   └── manifest.json      # Order and metadata
├── handlers/
└── core/
```

The test runner can then validate that handlers only access tables/columns that exist in the schema files.