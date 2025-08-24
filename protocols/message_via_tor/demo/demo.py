#!/usr/bin/env python3
"""
Message via Tor protocol demo using Textual TUI.
Shows multiple identities with Redux-like state inspection.
"""

import json
import sys
import copy
import time
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, Button, Label, RichLog, SelectionList
from textual.widgets.selection_list import Selection
from textual.reactive import reactive
from textual import events
from textual.message import Message
from rich.text import Text

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
        overflow-y: auto;
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
        overflow-y: auto;
    }
    
    #state-inspector {
        column-span: 1;
        height: 100%;
        border: solid magenta;
        overflow-y: auto;
    }
    
    .identity-dropdown {
        background: $boost;
        padding: 0 1;
        margin-bottom: 1;
        border: solid $primary;
    }
    
    .messages {
        height: 1fr;
        overflow-y: auto;
    }
    
    Input {
        dock: bottom;
    }
    
    .test-item {
        padding: 0 1;
    }
    
    .test-item.selected {
        background: $boost;
    }
    
    .state-change-item {
        padding: 0 1;
    }
    
    .state-change-item.selected {
        background: $boost;
    }
    """
    
    BINDINGS = [
        ("space", "load_test", "Load Test"),
        ("t", "tick", "Tick"),
        ("i", "create_identity", "Create Identity"),
        ("r", "reset", "Reset"),
        ("1", "focus_input1", "Input 1"),
        ("2", "focus_input2", "Input 2"),
        ("up", "test_up", "Test Up"),
        ("down", "test_down", "Test Down"),
        ("left", "change_left", "Change Left"),
        ("right", "change_right", "Change Right"),
        ("tab", "switch_identity", "Switch Identity"),
        ("q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.test_loader = TestLoader()
        self.selected_test = 12  # Default to test with Alice/Bob/Charlie
        self.selected_change = 0
        self.identity1_selected = 0
        self.identity2_selected = 0
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
        self._widget_counter = 0  # Counter for unique widget IDs
        
        # Load default test
        if self.selected_test < len(self.test_loader.tests):
            self.load_test_data()
    
    def load_test_data(self):
        """Load the selected test state"""
        if 0 <= self.selected_test < len(self.test_loader.tests):
            test = self.test_loader.tests[self.selected_test]
            given = test.get('given', {})
            
            before_state = copy.deepcopy(self.db.get('state', {}))
            
            # Load test state
            if 'db' in given:
                self.db = copy.deepcopy(given['db'])
            
            after_state = copy.deepcopy(self.db.get('state', {}))
            self.record_change(f"load_test: {test['name'][:50]}", before_state, after_state)
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        # Test list
        with VerticalScroll(id="test-list"):
            yield Label("Tests", classes="identity-label")
            for i, test in enumerate(self.test_loader.tests):
                classes = "test-item selected" if i == self.selected_test else "test-item"
                marker = "> " if i == self.selected_test else "  "
                yield Static(f"{marker}{test['name'][:40]}", classes=classes, id=f"test-{i}")
        
        # Identity 1
        with Vertical(id="identity1"):
            yield Static("Identity 1: None", classes="identity-dropdown", id="identity1-dropdown")
            yield RichLog(classes="messages", id="messages1", wrap=True)
            yield Input(placeholder="Type message...", id="input1")
        
        # Identity 2
        with Vertical(id="identity2"):
            yield Static("Identity 2: None", classes="identity-dropdown", id="identity2-dropdown")
            yield RichLog(classes="messages", id="messages2", wrap=True)
            yield Input(placeholder="Type message...", id="input2")
        
        # State changes
        with VerticalScroll(id="state-changes"):
            yield Label("State Changes", classes="identity-label")
            yield Container(id="changes-container")
        
        # State inspector
        with VerticalScroll(id="state-inspector"):
            yield Label("State Inspector", classes="identity-label")
            yield RichLog(id="inspector-log", wrap=True)
        
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
        
        # Update identity dropdowns
        if identities:
            if self.identity1_selected >= len(identities):
                self.identity1_selected = 0
            if self.identity2_selected >= len(identities):
                self.identity2_selected = min(1, len(identities) - 1)
                
            identity1 = identities[self.identity1_selected]
            self.query_one("#identity1-dropdown").update(f"Identity 1: {identity1['name']}")
            
            if len(identities) > 1:
                identity2 = identities[self.identity2_selected]
                self.query_one("#identity2-dropdown").update(f"Identity 2: {identity2['name']}")
            else:
                self.query_one("#identity2-dropdown").update("Identity 2: None")
            
            # Update messages for identity 1
            messages1 = self.get_messages_for_identity(identity1['pubkey'])
            log1 = self.query_one("#messages1", RichLog)
            log1.clear()
            for msg in messages1:
                sender = msg.get('sender', 'Unknown')[:15]
                text = msg.get('text', '')
                log1.write(f"{sender}: {text}")
            
            # Update messages for identity 2
            if len(identities) > 1:
                identity2 = identities[self.identity2_selected]
                messages2 = self.get_messages_for_identity(identity2['pubkey'])
                log2 = self.query_one("#messages2", RichLog)
                log2.clear()
                for msg in messages2:
                    sender = msg.get('sender', 'Unknown')[:15]
                    text = msg.get('text', '')
                    log2.write(f"{sender}: {text}")
        else:
            self.query_one("#identity1-dropdown").update("Identity 1: None")
            self.query_one("#identity2-dropdown").update("Identity 2: None")
            self.query_one("#messages1", RichLog).clear()
            self.query_one("#messages2", RichLog).clear()
        
        # Update state changes
        container = self.query_one("#changes-container")
        # Clear all existing children first
        try:
            container.remove_children()
        except Exception:
            pass
        
        # Mount new children with unique IDs
        for i, change in enumerate(self.state_changes):
            classes = "state-change-item selected" if i == self.selected_change else "state-change-item"
            marker = "> " if i == self.selected_change else "  "
            # Use counter to ensure unique IDs
            self._widget_counter += 1
            unique_id = f"change-{i}-{self._widget_counter}"
            static = Static(f"{marker}{change['operation']}", classes=classes, id=unique_id)
            container.mount(static)
        
        # Update state inspector
        inspector = self.query_one("#inspector-log", RichLog)
        inspector.clear()
        
        if self.selected_change < len(self.state_changes):
            change = self.state_changes[self.selected_change]
            inspector.write(Text("BEFORE:", style="bold yellow"))
            if change['before']:
                before_json = json.dumps(change['before'], indent=2)
                inspector.write(before_json)
            else:
                inspector.write("(empty)")
            
            inspector.write("")
            inspector.write(Text("AFTER:", style="bold green"))
            if change['after']:
                after_json = json.dumps(change['after'], indent=2)
                inspector.write(after_json)
            else:
                inspector.write("(empty)")
        else:
            inspector.write("Select a state change to inspect")
    
    def record_change(self, operation, before_state, after_state):
        """Record a state change"""
        self.state_changes.append({
            'operation': operation,
            'before': copy.deepcopy(before_state),
            'after': copy.deepcopy(after_state),
            'timestamp': time.time()
        })
        self.selected_change = len(self.state_changes) - 1
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message submission"""
        identities = self.get_identities()
        if not identities:
            return
        
        # Determine which identity sent the message
        if event.input.id == "input1":
            if self.identity1_selected >= len(identities):
                return
            identity = identities[self.identity1_selected]
        elif event.input.id == "input2":
            if self.identity2_selected >= len(identities):
                return
            identity = identities[self.identity2_selected]
        else:
            return
        
        text = event.value.strip()
        if not text:
            return
        
        # Send message via API
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        try:
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
                self.record_change(f"message.create: {text[:30]}", before_state, after_state)
        except Exception as e:
            self.record_change(f"message.create ERROR: {str(e)}", before_state, before_state)
        
        # Clear input and update display
        event.input.value = ""
        self.update_displays()
    
    def action_load_test(self) -> None:
        """Load the selected test"""
        self.load_test_data()
        self.update_displays()
    
    def action_tick(self) -> None:
        """Run one tick cycle"""
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        try:
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
        except Exception as e:
            self.record_change(f"tick ERROR: {str(e)}", before_state, before_state)
            self.update_displays()
    
    def action_create_identity(self) -> None:
        """Create a new identity"""
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        try:
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
        except Exception as e:
            self.record_change(f"identity.create ERROR: {str(e)}", before_state, before_state)
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
    
    def action_focus_input1(self) -> None:
        """Focus input 1"""
        self.query_one("#input1").focus()
    
    def action_focus_input2(self) -> None:
        """Focus input 2"""
        self.query_one("#input2").focus()
    
    def action_test_up(self) -> None:
        """Move test selection up"""
        if self.selected_test > 0:
            self.selected_test -= 1
            self.update_displays()
    
    def action_test_down(self) -> None:
        """Move test selection down"""
        if self.selected_test < len(self.test_loader.tests) - 1:
            self.selected_test += 1
            self.update_displays()
    
    def action_change_left(self) -> None:
        """Move state change selection left"""
        if self.selected_change > 0:
            self.selected_change -= 1
            self.update_displays()
    
    def action_change_right(self) -> None:
        """Move state change selection right"""
        if self.selected_change < len(self.state_changes) - 1:
            self.selected_change += 1
            self.update_displays()
    
    def action_switch_identity(self) -> None:
        """Switch between identities in the focused panel"""
        focused = self.focused
        identities = self.get_identities()
        
        if not identities:
            return
            
        if focused and focused.id == "input1":
            self.identity1_selected = (self.identity1_selected + 1) % len(identities)
            self.update_displays()
        elif focused and focused.id == "input2":
            self.identity2_selected = (self.identity2_selected + 1) % len(identities)
            self.update_displays()


if __name__ == "__main__":
    app = MessageViaTorDemo()
    app.run()