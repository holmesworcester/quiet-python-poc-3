#!/usr/bin/env python3
"""
Message via Tor protocol demo using Textual TUI.
Shows multiple identities with Redux-like state inspection.
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

class MessageViaTorDemo(App):
    """A Textual app to demo the message_via_tor protocol."""
    
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
        border: solid blue;
    }
    
    #identity4 {
        column-span: 1;
        height: 100%;
        border: solid blue;
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
        ("t", "tick", "Tick"),
        ("r", "reset", "Reset"),
        ("tab", "switch_identity", "Switch Identity"),
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.selected_change = 0
        self.identity1_selected = -1  # -1 means no identity
        self.identity2_selected = -1
        self.identity3_selected = -1
        self.identity4_selected = -1
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
        self.last_invite_links = {}  # Store invite links by identity
        self.identity_mapping = {}  # Map pubkey to original identity parameter
    
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        # Identity 1
        with Vertical(id="identity1"):
            yield Static("Identity 1: None", classes="identity-dropdown", id="identity1-dropdown")
            yield RichLog(classes="messages", id="messages1", wrap=True, markup=True)
            yield Input(placeholder="Type message or /help for commands...", id="input1")
        
        # Identity 2
        with Vertical(id="identity2"):
            yield Static("Identity 2: None", classes="identity-dropdown", id="identity2-dropdown")
            yield RichLog(classes="messages", id="messages2", wrap=True, markup=True)
            yield Input(placeholder="Type message or /help for commands...", id="input2")
        
        # Identity 3
        with Vertical(id="identity3"):
            yield Static("Identity 3: None", classes="identity-dropdown", id="identity3-dropdown")
            yield RichLog(classes="messages", id="messages3", wrap=True, markup=True)
            yield Input(placeholder="Type message or /help for commands...", id="input3")
        
        # Identity 4
        with Vertical(id="identity4"):
            yield Static("Identity 4: None", classes="identity-dropdown", id="identity4-dropdown")
            yield RichLog(classes="messages", id="messages4", wrap=True, markup=True)
            yield Input(placeholder="Type message or /help for commands...", id="input4")
        
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
        """Get messages visible to a specific identity using the API"""
        try:
            # Use the message.list API endpoint
            response = execute_api(
                "message_via_tor",
                "GET",
                f"/messages/{identity_pubkey}",
                data={"db": self.db}
            )
            
            if response.get("status") == 200:
                # Update our local db with any changes from the API
                if "db" in response.get("body", {}):
                    self.db = response["body"]["db"]
                
                # Return the messages from the API response
                return response.get("body", {}).get("messages", [])
            else:
                # Fall back to empty list on error
                return []
        except Exception as e:
            # Fall back to empty list on error
            return []
    
    def update_displays(self):
        """Update all display widgets"""
        identities = self.get_identities()
        
        # Update all 4 identity panels
        for i in range(1, 5):
            identity_selected = getattr(self, f"identity{i}_selected")
            dropdown = self.query_one(f"#identity{i}-dropdown")
            messages_log = self.query_one(f"#messages{i}", RichLog)
            input_field = self.query_one(f"#input{i}")
            
            if identity_selected >= 0 and identity_selected < len(identities):
                # Identity is selected - show identity info
                identity = identities[identity_selected]
                dropdown.update(f"Identity {i}: {identity['name']}")
                input_field.display = True
                messages_log.display = True
                
                # Update messages
                messages = self.get_messages_for_identity(identity['pubkey'])
                messages_log.clear()
                for msg in messages:
                    sender = msg.get('sender', 'Unknown')[:15]
                    text = msg.get('text', '')
                    messages_log.write(f"{sender}: {text}")
            else:
                # No identity selected - show input for commands
                dropdown.update(f"Identity {i}: None")
                input_field.display = True
                messages_log.display = True
                messages_log.clear()
        
        
        # Update state inspector
        inspector = self.query_one("#inspector-log", RichLog)
        inspector.clear()
        
        # Show current state
        inspector.write(Text("CURRENT STATE:", style="bold cyan"))
        state_json = json.dumps(self.db.get('state', {}), indent=2)
        inspector.write(state_json)
    
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
        """Handle message submission or commands"""
        # Determine which input sent this
        input_id = event.input.id
        if not input_id.startswith("input"):
            return
            
        identity_num = int(input_id[-1])
        text = event.value.strip()
        
        # Clear input immediately
        event.input.value = ""
        
        if not text:
            return
        
        # Handle slash commands
        if text.startswith("/"):
            await self.handle_command(identity_num, text)
            return
        
        # Regular message - need an identity selected
        identities = self.get_identities()
        if not identities:
            return
            
        identity_selected = getattr(self, f"identity{identity_num}_selected")
        if identity_selected < 0 or identity_selected >= len(identities):
            return
        identity = identities[identity_selected]
        
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
            else:
                # Show API error in current message log
                messages_log = self.query_one(f"#messages{identity_num}", RichLog)
                messages_log.write(f"[red]Failed to send message (status {response.get('status')}):[/red]")
                error_body = response.get('body', {})
                if isinstance(error_body, dict):
                    error_msg = error_body.get('error', 'Unknown error')
                else:
                    error_msg = str(error_body)
                messages_log.write(f"[red]{error_msg}[/red]")
        except Exception as e:
            messages_log = self.query_one(f"#messages{identity_num}", RichLog)
            messages_log.write(f"[red]Exception sending message: {str(e)}[/red]")
            self.record_change(f"message.create ERROR: {str(e)}", before_state, before_state)
        
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
    
    async def handle_command(self, identity_num: int, command: str) -> None:
        """Handle slash commands."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Get message log for feedback
        messages_log = self.query_one(f"#messages{identity_num}", RichLog)
        
        if cmd == "/create":
            if not args:
                messages_log.write("[red]Usage: /create <name>[/red]")
                return
            await self.create_identity(identity_num, args)
            messages_log.write(f"[green]Created identity: {args}[/green]")
            
        elif cmd == "/invite":
            # Generate an invite link for current identity
            identity_selected = getattr(self, f"identity{identity_num}_selected")
            if identity_selected < 0:
                messages_log.write("[red]Create an identity first with /create <name>[/red]")
                return
            identities = self.get_identities()
            if identity_selected >= len(identities):
                messages_log.write("[red]No identity selected[/red]")
                return
            identity = identities[identity_selected]
            # Generate invite link using the invite API
            try:
                response = execute_api(
                    "message_via_tor",
                    "POST",
                    f"/identities/{identity['id']}/invite",
                    data={"db": self.db}
                )
                if response.get("status") in [200, 201]:
                    # Look for inviteLink (API now converts to camelCase)
                    invite_link = response["body"].get("inviteLink", "Error generating invite")
                    
                    # Store the link for this identity
                    self.last_invite_links[identity['id']] = invite_link
                    
                    messages_log.write(f"[green]Your invite link has been generated![/green]")
                    messages_log.write("")  # Empty line
                    
                    # Remove any existing invite link display first
                    try:
                        old_link = self.query_one(f"#invite-link-{identity_num}")
                        old_link.remove()
                    except:
                        pass
                    
                    # Create a temporary TextArea to show the link (selectable)
                    # Find the parent container
                    identity_container = self.query_one(f"#identity{identity_num}")
                    
                    # Create a read-only TextArea with the invite link
                    link_display = TextArea(invite_link, read_only=True, id=f"invite-link-{identity_num}")
                    link_display.styles.height = 3
                    link_display.styles.margin = (1, 0)
                    
                    # Mount it at the top of the identity container
                    identity_container.mount(link_display, after=f"#identity{identity_num}-dropdown")
                    
                    # Show instructions
                    messages_log.write("[yellow]Select the text above to copy the invite link[/yellow]")
                    messages_log.write("[green]/link[/green] - Show the invite link again")
                    messages_log.write("")
                    messages_log.write("[dim]Share this link with others to let them join[/dim]")
                else:
                    messages_log.write(f"[red]API Error (status {response.get('status')}):[/red]")
                    error_body = response.get('body', {})
                    if isinstance(error_body, dict):
                        error_msg = error_body.get('error', 'Unknown error')
                    else:
                        error_msg = str(error_body)
                    messages_log.write(f"[red]{error_msg}[/red]")
            except Exception as e:
                messages_log.write(f"[red]Exception: {str(e)}[/red]")
                
        elif cmd == "/join":
            if not args:
                messages_log.write("[red]Usage: /join <name> <invite-link>[/red]")
                return
            parts = args.split(maxsplit=1)
            if len(parts) < 2:
                messages_log.write("[red]Usage: /join <name> <invite-link>[/red]")
                messages_log.write("[dim]Example: /join Alice https://invite.link/xyz123[/dim]")
                return
            name = parts[0]
            invite_link = parts[1]
            success = await self.join_with_invite(identity_num, name, invite_link)
            if success:
                messages_log.write(f"[green]Successfully joined as {name}![/green]")
            else:
                messages_log.write(f"[red]Failed to join with invite link[/red]")
            
        elif cmd == "/link":
            # Show the last generated invite link for current identity
            identity_selected = getattr(self, f"identity{identity_num}_selected")
            if identity_selected < 0:
                messages_log.write("[red]No identity selected[/red]")
                return
            identities = self.get_identities()
            if identity_selected >= len(identities):
                messages_log.write("[red]Invalid identity selected[/red]")
                return
            identity = identities[identity_selected]
            
            if identity['id'] in self.last_invite_links:
                invite_link = self.last_invite_links[identity['id']]
                
                # Remove any existing invite link display
                try:
                    old_link = self.query_one(f"#invite-link-{identity_num}")
                    old_link.remove()
                except:
                    pass
                
                # Create a new TextArea to show the link
                identity_container = self.query_one(f"#identity{identity_num}")
                link_display = TextArea(invite_link, read_only=True, id=f"invite-link-{identity_num}")
                link_display.styles.height = 3
                link_display.styles.margin = (1, 0)
                identity_container.mount(link_display, after=f"#identity{identity_num}-dropdown")
                
                messages_log.write("[yellow]Select the text above to copy the invite link[/yellow]")
            else:
                messages_log.write("[yellow]No invite link generated yet. Use /invite to create one.[/yellow]")
                
        elif cmd == "/help":
            messages_log.write("[bold cyan]Available commands:[/bold cyan]")
            messages_log.write("")
            messages_log.write("[green]/create <name>[/green] - Create a new identity with the specified name")
            messages_log.write("[green]/invite[/green] - Generate an invite link to share with others")
            messages_log.write("[green]/link[/green] - Show the last generated invite link")
            messages_log.write("[green]/join <name> <invite-link>[/green] - Join a group using an invite link")
            messages_log.write("[green]/help[/green] - Show this help message")
            messages_log.write("")
            messages_log.write("[dim]Regular messages: Just type and press Enter to send[/dim]")
            messages_log.write("[dim]Navigation: Use Tab to switch between identities[/dim]")
            
        else:
            messages_log.write(f"[red]Unknown command: {cmd}[/red]")
            messages_log.write("Type /help for available commands")
    
    async def create_identity(self, identity_num: int, name: str) -> None:
        """Create a new identity."""
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        try:
            response = execute_api(
                "message_via_tor",
                "POST",
                "/identities",
                data={
                    "name": name,
                    "db": self.db
                }
            )
            
            if response.get("status") == 201:
                self.db = response["body"]["db"]
                after_state = copy.deepcopy(self.db.get('state', {}))
                self.record_change(f"identity.create: {name}", before_state, after_state)
                
                # Set this identity as selected for the panel
                identities = self.get_identities()
                for i, identity in enumerate(identities):
                    if identity['name'] == name:
                        setattr(self, f"identity{identity_num}_selected", i)
                        break
                
                self.update_displays()
            else:
                # Show API error in message log
                messages_log = self.query_one(f"#messages{identity_num}", RichLog)
                messages_log.write(f"[red]API Error (status {response.get('status')}):[/red]")
                error_body = response.get('body', {})
                if isinstance(error_body, dict):
                    error_msg = error_body.get('error', 'Unknown error')
                else:
                    error_msg = str(error_body)
                messages_log.write(f"[red]{error_msg}[/red]")
                
        except Exception as e:
            # Show exception in message log
            messages_log = self.query_one(f"#messages{identity_num}", RichLog)
            messages_log.write(f"[red]Exception: {str(e)}[/red]")
            self.record_change(f"identity.create ERROR: {str(e)}", before_state, before_state)
            self.update_displays()
    
    async def join_with_invite(self, identity_num: int, name: str, invite_link: str) -> bool:
        """Join using an invite link."""
        messages_log = self.query_one(f"#messages{identity_num}", RichLog)
        
        # First check if we already have an identity in this slot
        identity_selected = getattr(self, f"identity{identity_num}_selected")
        if identity_selected >= 0:
            messages_log.write("[yellow]Identity already exists in this slot. Use an empty slot.[/yellow]")
            return False
            
        before_state = copy.deepcopy(self.db.get('state', {}))
        
        try:
            # Call the join API endpoint with the invite link and name
            response = execute_api(
                "message_via_tor",
                "POST",
                "/join",
                data={
                    "name": name,
                    "inviteLink": invite_link,
                    "db": self.db
                }
            )
            
            if response.get("status") == 201:
                self.db = response["body"]["db"]
                after_state = copy.deepcopy(self.db.get('state', {}))
                self.record_change(f"identity.join: {name}", before_state, after_state)
                
                # Get the newly created identity and set it as selected
                identities = self.get_identities()
                if identities:
                    # Find the identity we just created by name
                    for i, identity in enumerate(identities):
                        if identity['name'] == name:
                            setattr(self, f"identity{identity_num}_selected", i)
                            break
                    self.update_displays()
                    return True
                else:
                    messages_log.write("[red]Join succeeded but no identity was created[/red]")
                    return False
            else:
                messages_log.write(f"[red]API Error (status {response.get('status')}):[/red]")
                error_body = response.get('body', {})
                if isinstance(error_body, dict):
                    error_msg = error_body.get('error', 'Unknown error')
                else:
                    error_msg = str(error_body)
                messages_log.write(f"[red]{error_msg}[/red]")
                return False
                
        except Exception as e:
            messages_log.write(f"[red]Exception: {str(e)}[/red]")
            self.record_change(f"identity.join ERROR: {str(e)}", before_state, before_state)
            return False
    
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
        elif focused and focused.id == "input3":
            self.identity3_selected = (self.identity3_selected + 1) % len(identities)
            self.update_displays()
        elif focused and focused.id == "input4":
            self.identity4_selected = (self.identity4_selected + 1) % len(identities)
            self.update_displays()


if __name__ == "__main__":
    app = MessageViaTorDemo()
    app.run()