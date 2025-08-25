# Playground.py Planning Document

## Overview
A general-purpose TUI/CLI framework for interacting with protocols, designed to be LLM-testable and configurable via YAML. This tool will provide a flexible interface for testing and exploring protocol functionality through multiple windows with command-based interaction.

## Core Requirements

### 1. TUI and CLI Interface
- **TUI Mode**: Interactive terminal UI with multiple windows using Textual
- **CLI Mode**: Command-line interface for LLM testing and scripting
- **Protocol Agnostic**: Pass a protocol path like test_runner.py

### 2. YAML Configuration
- Settings file defines window layout, default commands, and saved states
- Support for multiple named configurations (profiles)

### 3. Window System
- Each window contains:
  - Command entry field
  - Output log/list area
  - Window-specific state and history
- Grid layouts: 1x1, 1x2, 1x4, 2x2, 2x3, 3x3, etc.
- Terminal window can be resized

### 4. Command System
- IRC-style `/` commands for window control
- Each window maintains its own command context
- Command history and tab completion
- Aliasing and variable substitution

## Architecture

### Window Manager
```python
class Window:
    id: str
    title: str
    command_history: List[str]
    default_command: Optional[str]
    output_buffer: List[Any]
    current_filter: Optional[Filter]
    aliases: Dict[str, str]
```

### Command Types

#### Window-Specific Commands
- `/api <endpoint> [params]` - Make API call to protocol
- `/default <command>` - Set default command for plain input
- `/map <template>` - Transform output items
- `/reduce <template>` - Aggregate output items
- `/filter <regex>` - Filter output display
- `/alias <name> <command>` - Create command alias
- `/clear` - Clear window output
- `/history` - Show command history
- `/repeat <n> <command>` - Run command n times
- `/interval <seconds> <command>` - Run command periodically
- `/stop` - Stop any running intervals

#### Global Commands
- `/layout <grid>` - Change window layout (e.g., 2x2)
- `/protocol <path>` - Switch protocol
- `/reset-db` - Clear protocol database
- `/save [name]` - Save current configuration
- `/save-as <name>` - Save configuration with new name
- `/load <name>` - Load saved configuration
- `/window <id>` - Focus specific window
- `/title <id> <title>` - Rename window
- `/quit` - Exit application

### Data Transformation Templates

#### Map Templates
- `json:<path>` - Extract JSON path
- `regex:<pattern>` - Extract regex groups
- `format:<template>` - String formatting
- `python:<expr>` - Python expression

#### Reduce Templates
- `count` - Count items
- `sum:<field>` - Sum numeric field
- `group:<field>` - Group by field
- `unique:<field>` - Unique values
- `python:<expr>` - Custom reduction

## YAML Configuration Schema

```yaml
# playground_config.yaml
version: 1.0
protocol: protocols/message_via_tor
layout: 2x2

# Global settings
api:
  base_url: http://localhost:8000
  timeout: 30

# Window definitions
windows:
  - id: identities
    title: "Identities"
    position: [0, 0]  # row, col in grid
    default_command: "/api GET /identities"
    aliases:
      create: "/api POST /identities name={name}"
      list: "/api GET /identities"
    auto_refresh: 5  # seconds

  - id: messages
    title: "Messages"
    position: [0, 1]
    default_command: "/api GET /messages"
    map: "format:{sender}: {content}"
    
  - id: events
    title: "Event Stream"
    position: [1, 0]
    default_command: "/api GET /events"
    filter: "type=message_created"
    
  - id: console
    title: "Console"
    position: [1, 1]
    # No default command - free-form interaction

# Saved command sets
command_sets:
  demo_setup:
    - window: identities
      commands:
        - "/api POST /identities name=Alice"
        - "/api POST /identities name=Bob"
    - window: console
      commands:
        - "/protocol protocols/message_via_tor"
```

## CLI Mode Usage

```bash
# Interactive TUI
python core/playground.py protocols/message_via_tor

# Load specific config
python core/playground.py protocols/message_via_tor --config demo.yaml

# CLI mode - single command
python core/playground.py protocols/message_via_tor --cli "/api GET /identities"

# CLI mode - command file
python core/playground.py protocols/message_via_tor --cli-file commands.txt

# CLI mode - interactive
python core/playground.py protocols/message_via_tor --cli-interactive
```

## Implementation Phases

### Phase 1: Core Framework
1. Window manager with basic grid layouts
2. Command parser and executor
3. YAML configuration loader
4. Basic API integration

### Phase 2: Advanced Features
1. Data transformation (map/reduce)
2. Command aliasing and variables
3. Auto-refresh and intervals
4. Command history and persistence

### Phase 3: Polish
1. Tab completion
2. Syntax highlighting
3. Export/import functionality
4. Plugin system for custom commands

## Example: Recreating demo.py

Using playground.py, we can recreate the demo.py functionality:

```yaml
# message_demo.yaml
protocol: protocols/message_via_tor
layout: 2x2

windows:
  - id: users
    title: "Users"
    default_command: "/api GET /identities"
    aliases:
      new: "/api POST /identities name={1}"
      select: "/set current_user {1}"
    
  - id: messages  
    title: "Messages"
    default_command: "/api GET /messages?identity={current_user}"
    map: "format:[{timestamp}] {sender}: {content}"
    auto_refresh: 2
    
  - id: compose
    title: "Compose"
    aliases:
      send: "/api POST /messages identity={current_user} recipient={1} content={2}"
    default_command: "send"
    
  - id: events
    title: "Events"
    default_command: "/api GET /events?identity={current_user}"
    filter: "message_"
    reduce: "count"
```

## Testing Strategy

### LLM Testing
- All commands executable via CLI
- Deterministic output formats
- Scriptable command sequences
- JSON output mode for parsing

### Unit Tests
- Command parser
- Window manager
- Data transformers
- Configuration loader

### Integration Tests
- Protocol API calls
- Multi-window coordination
- Configuration persistence
- Event streaming

## Security Considerations
- Sandbox Python expressions
- Validate API inputs
- Rate limit commands
- Secure credential storage

## Future Extensions
- WebSocket support for real-time updates
- Record/replay functionality
- Export to various formats
- Multi-protocol support
- Remote playground connections