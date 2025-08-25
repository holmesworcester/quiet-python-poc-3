#!/usr/bin/env python3
"""
Persistent version of the Message via Tor protocol demo.
This version maintains database state between sessions.
Based on demo.py but with persistence.
"""

import json
import sys
import os
import copy
import time
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, Grid
from textual.widgets import Header, Footer, Static, Input, Label, RichLog, TextArea, Button
from textual.widgets.selection_list import Selection
from textual.reactive import reactive
from textual import events
from textual.message import Message
from rich.text import Text

# Add the root directory to path for core imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from core.api import execute_api

# Change to project root directory for API calls
os.chdir(project_root)

class PersistentMessageViaTorDemo(App):
    """A persistent Textual app to demo the message_via_tor protocol."""
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 5 1;
        grid-gutter: 1;
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
    
    #identity3 {
        column-span: 1;
        height: 100%;
        border: solid green;
    }
    
    #identity4 {
        column-span: 1;
        height: 100%;
        border: solid green;
    }
    
    #state_changes {
        column-span: 1;
        height: 100%;
        border: solid yellow;
    }
    
    .identity-header {
        height: 3;
        background: $boost;
        padding: 0 1;
    }
    
    RichLog {
        height: 100%;
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
        ("t", "tick", "Tick"),
        ("tab", "switch_identity", "Switch Identity"),
        ("r", "reset_db", "Reset DB"),
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]
    
    def __init__(self, reset_db=False):
        super().__init__()
        self.selected_change = 0
        self.identity1_selected = -1  # -1 means no identity
        self.identity2_selected = -1
        self.identity3_selected = -1
        self.identity4_selected = -1
        
        # Set up SQL database path
        self.db_path = 'persistent_demo.db'
        os.environ['API_DB_PATH'] = self.db_path
        
        # Only reset if explicitly requested
        if reset_db and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                self.log(f"Database reset.")
            except Exception as e:
                self.log(f"Could not reset database: {e}")
        elif os.path.exists(self.db_path):
            self.log(f"Using existing database: {self.db_path}")
        
        self.state_changes = []
        self.active_identity = 1  # Which identity input is active
        
        # Store identities list
        self.identities = []
        
        # Store invite links
        self.invite_links = {}
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        # Identity 1
        with Container(id="identity1"):
            yield Label("Identity 1", classes="identity-header")
            yield RichLog(highlight=True, markup=True)
            yield Input(placeholder="Enter message or /command")
        
        # Identity 2  
        with Container(id="identity2"):
            yield Label("Identity 2", classes="identity-header")
            yield RichLog(highlight=True, markup=True)
            yield Input(placeholder="Enter message or /command")
            
        # Identity 3
        with Container(id="identity3"):
            yield Label("Identity 3", classes="identity-header")
            yield RichLog(highlight=True, markup=True)
            yield Input(placeholder="Enter message or /command")
            
        # Identity 4
        with Container(id="identity4"):
            yield Label("Identity 4", classes="identity-header")
            yield RichLog(highlight=True, markup=True)
            yield Input(placeholder="Enter message or /command")
        
        # State changes panel
        with VerticalScroll(id="state_changes"):
            yield Label("State Changes", classes="identity-header")
            yield Container(id="changes_list")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app starts."""
        self.title = "Message via Tor Demo (Persistent)"
        self.sub_title = "Press 'r' to reset database"
        
        # Load existing identities
        self.refresh_identities()
        
        # Focus on first input
        self.query_one("#identity1 Input").focus()
        
    def refresh_identities(self):
        """Load identities from database."""
        try:
            response = execute_api(
                protocol_name="message_via_tor",
                method="GET",
                path="/identities",
                data={}
            )
            
            if response.get("status") == 200:
                self.identities = response["body"].get("identities", [])
                
                # Update UI to show existing identities
                for i, identity in enumerate(self.identities[:4]):  # Max 4 identities in UI
                    identity_num = i + 1
                    header = self.query_one(f"#identity{identity_num} Label")
                    header.update(f"Identity {identity_num}: {identity.get('name', 'Unknown')}")
                    
                    # Log that we loaded this identity
                    log = self.query_one(f"#identity{identity_num} RichLog")
                    log.write(f"[green]Loaded existing identity: {identity.get('name')}[/green]")
                    
                    # Update selection
                    setattr(self, f"identity{identity_num}_selected", i)
                    
                if self.identities:
                    self.log(f"Loaded {len(self.identities)} existing identities")
                    
        except Exception as e:
            self.log(f"Error loading identities: {e}")
    
    def log(self, message: str) -> None:
        """Log a message to the state changes panel."""
        changes_list = self.query_one("#changes_list")
        
        # Create state change entry
        change_entry = Static(f"[{time.strftime('%H:%M:%S')}] {message}", classes="state-change-item")
        changes_list.mount(change_entry)
        
        # Keep only last 50 changes
        if len(changes_list.children) > 50:
            changes_list.children[0].remove()
        
        # Scroll to bottom
        self.query_one("#state_changes").scroll_end()
    
    def action_reset_db(self) -> None:
        """Reset the database."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                self.log("Database reset! Restart the app to see changes.")
                self.identities = []
                self.invite_links = {}
                
                # Reset all identity headers
                for i in range(1, 5):
                    header = self.query_one(f"#identity{i} Label")
                    header.update(f"Identity {i}")
                    setattr(self, f"identity{i}_selected", -1)
                    
            except Exception as e:
                self.log(f"Error resetting database: {e}")
    
    # ... rest of the methods from original demo.py ...
    # (I'll include the key methods for handling messages and identities)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        # Determine which identity sent this
        identity_num = None
        for i in range(1, 5):
            if event.input.id == self.query_one(f"#identity{i} Input").id:
                identity_num = i
                break
        
        if not identity_num:
            return
        
        value = event.value.strip()
        if not value:
            return
        
        # Clear input
        event.input.value = ""
        
        # Get the log for this identity
        log = self.query_one(f"#identity{identity_num} RichLog")
        
        # Handle commands
        if value.startswith("/"):
            self.handle_command(identity_num, value, log)
        else:
            self.send_message(identity_num, value, log)
    
    def handle_command(self, identity_num: int, command: str, log: RichLog) -> None:
        """Handle slash commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "/create":
            if not args:
                log.write("[red]Usage: /create <name>[/red]")
                return
            self.create_identity(identity_num, args, log)
            
        elif cmd == "/invite":
            self.generate_invite(identity_num, log)
            
        elif cmd == "/join":
            if not args:
                log.write("[red]Usage: /join <invite_link>[/red]")
                return
            self.join_network(identity_num, args, log)
            
        elif cmd == "/list":
            self.list_identities(log)
            
        else:
            log.write(f"[red]Unknown command: {cmd}[/red]")
    
    def create_identity(self, identity_num: int, name: str, log: RichLog) -> None:
        """Create a new identity."""
        try:
            response = execute_api(
                protocol_name="message_via_tor",
                method="POST",
                path="/identities",
                data={"name": name}
            )
            
            if response.get("status") == 201:
                identity_id = response["body"]["identityId"]
                log.write(f"[green]Created identity: {name} ({identity_id[:8]}...)[/green]")
                
                # Update header
                header = self.query_one(f"#identity{identity_num} Label")
                header.update(f"Identity {identity_num}: {name}")
                
                # Refresh identities list
                self.refresh_identities()
                
                # Update selection for this identity
                for i, identity in enumerate(self.identities):
                    if identity.get("identityId") == identity_id:
                        setattr(self, f"identity{identity_num}_selected", i)
                        break
                
                self.log(f"Identity {identity_num} created: {name}")
            else:
                log.write(f"[red]Failed to create identity: {response}[/red]")
                
        except Exception as e:
            log.write(f"[red]Error creating identity: {e}[/red]")
    
    def generate_invite(self, identity_num: int, log: RichLog) -> None:
        """Generate an invite link."""
        selected = getattr(self, f"identity{identity_num}_selected")
        if selected < 0 or selected >= len(self.identities):
            log.write("[red]No identity selected. Create one first.[/red]")
            return
        
        identity = self.identities[selected]
        identity_id = identity.get("identityId")
        
        try:
            response = execute_api(
                protocol_name="message_via_tor",
                method="POST",
                path=f"/identities/{identity_id}/invite",
                data={}
            )
            
            if response.get("status") in [200, 201]:
                invite_link = response["body"].get("inviteLink")
                if invite_link:
                    log.write(f"[green]Invite link generated:[/green]")
                    log.write(f"[yellow]{invite_link}[/yellow]")
                    self.invite_links[identity_id] = invite_link
                    self.log(f"Identity {identity_num} generated invite")
            else:
                log.write(f"[red]Failed to generate invite: {response}[/red]")
                
        except Exception as e:
            log.write(f"[red]Error generating invite: {e}[/red]")
    
    def action_switch_identity(self) -> None:
        """Switch between identity inputs."""
        # Find current focused input
        for i in range(1, 5):
            input_widget = self.query_one(f"#identity{i} Input")
            if input_widget.has_focus:
                # Move to next identity
                next_identity = (i % 4) + 1
                self.query_one(f"#identity{next_identity} Input").focus()
                self.active_identity = next_identity
                break
    
    def action_tick(self) -> None:
        """Run a tick."""
        try:
            response = execute_api(
                protocol_name="message_via_tor",
                method="POST",
                path="/tick",
                data={}
            )
            
            self.log(f"Tick completed: {response.get('body', {})}")
            
            # Refresh messages for all identities
            self.refresh_all_messages()
            
        except Exception as e:
            self.log(f"Tick error: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Persistent Message via Tor Demo')
    parser.add_argument('--reset', action='store_true', help='Reset database on startup')
    args = parser.parse_args()
    
    app = PersistentMessageViaTorDemo(reset_db=args.reset)
    app.run()