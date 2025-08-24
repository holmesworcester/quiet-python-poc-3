#!/usr/bin/env python3
"""
Message via Tor demo using Textual for proper TUI.
"""

import json
import sys
import copy
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, Button, Label, RichLog, Tree
from textual.reactive import reactive
from textual import events
from textual.message import Message

# Add the root directory to path for core imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from core.api import execute_api


class TestLoader:
    def __init__(self):
        self.tests = []
        self.load_tests()
    
    def load_tests(self):
        handlers_dir = Path(__file__).parent.parent / "handlers"
        for handler_file in handlers_dir.glob("*/*_handler.json"):
            try:
                with open(handler_file) as f:
                    handler_data = json.load(f)
                
                # Load projector tests
                projector = handler_data.get("projector", {})
                if "tests" in projector:
                    for test in projector["tests"]:
                        self.tests.append({
                            "name": f"{handler_file.parent.name}.projector: {test.get('description', 'No description')}",
                            "given": test.get("given", {}),
                            "type": "projector"
                        })
                
                # Load command tests
                commands = handler_data.get("commands", {})
                for cmd_name, cmd_data in commands.items():
                    if "tests" in cmd_data:
                        for test in cmd_data["tests"]:
                            self.tests.append({
                                "name": f"{handler_file.parent.name}.{cmd_name}: {test.get('description', 'No description')}",
                                "given": test.get("given", {}),
                                "type": "command"
                            })
            except Exception as e:
                print(f"Error loading {handler_file}: {e}")


class MessageViaTorDemo(App):
    """A Textual app to demo the message_via_tor protocol."""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 5 1;
        grid-gutter: 1;
    }
    
    #test-list {
        column-span: 1;
        height: 100%;
        border: solid green;
    }
    
    #identity1 {
        column-span: 1;
        height: 100%;
        border: solid blue;
    }
    
    #identity2 {
        column-span: 1;
        height: 100%;
        border: solid blue;
    }
    
    #state-changes {
        column-span: 1;
        height: 100%;
        border: solid yellow;
    }
    
    #state-inspector {
        column-span: 1;
        height: 100%;
        border: solid magenta;
    }
    
    .identity-label {
        background: $boost;
        padding: 0 1;
        margin-bottom: 1;
    }
    
    .messages {
        height: 1fr;
        overflow: auto;
    }
    
    Input {
        dock: bottom;
    }
    """
    
    BINDINGS = [
        ("t", "tick", "Tick"),
        ("i", "create_identity", "Create Identity"),
        ("r", "reset", "Reset"),
        ("q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.test_loader = TestLoader()
        self.selected_test = 12  # Default to test with Alice/Bob/Charlie
        self.db = {
            'state': {
                'identities': [],
                'peers': [],
                'messages': [],
                'outgoing': []
            },
            'eventStore': []
        }
        self.state_changes = []
        self.selected_change = 0
        
        # Load default test
        if self.selected_test < len(self.test_loader.tests):
            test = self.test_loader.tests[self.selected_test]
            if 'db' in test.get('given', {}):
                self.db = copy.deepcopy(test['given']['db'])
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        # Test list
        with VerticalScroll(id="test-list"):
            yield Label("Tests", classes="identity-label")
            for i, test in enumerate(self.test_loader.tests):
                marker = "> " if i == self.selected_test else "  "
                yield Static(f"{marker}{test['name'][:30]}")
        
        # Identity 1
        with Vertical(id="identity1"):
            yield Label("Identity 1", classes="identity-label")
            yield RichLog(classes="messages", id="messages1")
            yield Input(placeholder="Type message...", id="input1")
        
        # Identity 2
        with Vertical(id="identity2"):
            yield Label("Identity 2", classes="identity-label")
            yield RichLog(classes="messages", id="messages2")
            yield Input(placeholder="Type message...", id="input2")
        
        # State changes
        with VerticalScroll(id="state-changes"):
            yield Label("State Changes", classes="identity-label")
            yield RichLog(id="changes-log")
        
        # State inspector
        with VerticalScroll(id="state-inspector"):
            yield Label("State Inspector", classes="identity-label")
            yield RichLog(id="inspector-log")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app starts."""
        self.update_displays()
    
    def get_identities(self):
        """Get list of identities from current state"""
        identities = []
        state = self.db.get('state', {})
        
        # Handle both dict and list formats
        identity_data = state.get('identities', [])
        if isinstance(identity_data, dict):
            for key, value in identity_data.items():
                identities.append({
                    'id': key,
                    'name': value.get('name', key),
                    'pubkey': value.get('keypair', {}).get('public', key)
                })
        elif isinstance(identity_data, list):
            for item in identity_data:
                identities.append({
                    'id': item.get('pubkey', 'unknown'),
                    'name': item.get('name', 'Unknown'),
                    'pubkey': item.get('pubkey', 'unknown')
                })
        
        return identities
    
    def get_messages_for_identity(self, identity_pubkey):
        """Get messages visible to a specific identity"""
        messages = self.db.get('state', {}).get('messages', [])
        identity_messages = []
        
        for msg in messages:
            # Show messages received by this identity or sent by this identity
            if (msg.get('received_by') == identity_pubkey or 
                msg.get('sender') == identity_pubkey):
                # Skip unknown peer messages
                if not msg.get('unknown_peer', False):
                    identity_messages.append(msg)
        
        return identity_messages
    
    def update_displays(self):
        """Update all display widgets"""
        identities = self.get_identities()
        
        # Update identity labels
        if identities:
            self.query_one("#identity1 Label").update(f"Identity: {identities[0]['name']}" if identities else "No Identity")
            if len(identities) > 1:
                self.query_one("#identity2 Label").update(f"Identity: {identities[1]['name']}")
            else:
                self.query_one("#identity2 Label").update("No Identity")
            
            # Update messages
            if identities:
                messages1 = self.get_messages_for_identity(identities[0]['pubkey'])
                log1 = self.query_one("#messages1", RichLog)
                log1.clear()
                for msg in messages1:
                    sender = msg.get('sender', 'Unknown')[:10]
                    text = msg.get('text', '')
                    log1.write(f"{sender}: {text}")
            
            if len(identities) > 1:
                messages2 = self.get_messages_for_identity(identities[1]['pubkey'])
                log2 = self.query_one("#messages2", RichLog)
                log2.clear()
                for msg in messages2:
                    sender = msg.get('sender', 'Unknown')[:10]
                    text = msg.get('text', '')
                    log2.write(f"{sender}: {text}")
        
        # Update state changes
        changes_log = self.query_one("#changes-log", RichLog)
        changes_log.clear()
        for change in self.state_changes[-20:]:
            changes_log.write(change['operation'])
        
        # Update state inspector
        if self.selected_change < len(self.state_changes):
            change = self.state_changes[self.selected_change]
            inspector = self.query_one("#inspector-log", RichLog)
            inspector.clear()
            inspector.write("BEFORE:")
            inspector.write(json.dumps(change['before'], indent=2)[:200])
            inspector.write("\nAFTER:")
            inspector.write(json.dumps(change['after'], indent=2)[:200])
    
    def record_change(self, operation, before_state, after_state):
        """Record a state change"""
        self.state_changes.append({
            'operation': operation,
            'before': copy.deepcopy(before_state),
            'after': copy.deepcopy(after_state),
        })
        self.selected_change = len(self.state_changes) - 1
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission"""
        identities = self.get_identities()
        if not identities:
            return
        
        # Determine which identity sent the message
        if event.input.id == "input1" and identities:
            identity = identities[0]
        elif event.input.id == "input2" and len(identities) > 1:
            identity = identities[1]
        else:
            return
        
        text = event.value.strip()
        if not text:
            return
        
        # Send message via API
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        response = execute_api(
            "message_via_tor",
            "POST", 
            "/messages",
            data={
                "text": text,
                "db": self.db
            },
            identity=identity['id']
        )
        
        if response.get("status") == 201:
            self.db = response["body"]["db"]
            after_state = copy.deepcopy(self.db.get('state', {}))
            self.record_change(f"message: {text[:20]}", before_state, after_state)
        
        # Clear input and update display
        event.input.value = ""
        self.update_displays()
    
    def action_tick(self) -> None:
        """Run one tick cycle"""
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        response = execute_api(
            "message_via_tor",
            "POST",
            "/tick",
            data={"db": self.db}
        )
        
        if response.get("status") == 200:
            self.db = response["body"]["db"]
            after_state = copy.deepcopy(self.db.get('state', {}))
            self.record_change("tick", before_state, after_state)
            self.update_displays()
    
    def action_create_identity(self) -> None:
        """Create a new identity"""
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        response = execute_api(
            "message_via_tor",
            "POST",
            "/identities",
            data={
                "name": f"User{len(self.get_identities())+1}",
                "db": self.db
            }
        )
        
        if response.get("status") == 201:
            self.db = response["body"]["db"]
            after_state = copy.deepcopy(self.db.get('state', {}))
            self.record_change("identity.create", before_state, after_state)
            self.update_displays()
    
    def action_reset(self) -> None:
        """Reset state"""
        before_state = copy.deepcopy(self.db.get('state', {}))
        self.db = {
            'state': {
                'identities': [],
                'peers': [],
                'messages': [],
                'outgoing': []
            },
            'eventStore': []
        }
        self.state_changes = []
        self.selected_change = 0
        self.record_change("reset", before_state, {})
        self.update_displays()


if __name__ == "__main__":
    app = MessageViaTorDemo()
    app.run()