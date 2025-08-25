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
from textual.timer import Timer

# Add the root directory to path for core imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
from core.api import execute_api

# Change to project root directory for API calls
os.chdir(project_root)

# Store reference to original execute_api
original_execute_api = execute_api

class MessageViaTorDemo(App):
    """A Textual app to demo the message_via_tor protocol."""
    
    # Set title to empty to remove title bar
    TITLE = ""
    # Disable sub-title
    SUB_TITLE = ""
    # Disable the header completely
    ENABLE_COMMAND_PALETTE = False
    
    # Class variable to control database reset
    RESET_DB = True
    
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 2;
        grid-rows: 1fr 1fr;
        grid-gutter: 1;
    }
    
    /* Remove any loading bars */
    LoadingIndicator {
        display: none !important;
    }
    
    #controls {
        column-span: 2;
        height: auto;
        dock: top;
        background: $surface;
        border: solid $primary;
        layout: horizontal;
        padding: 0 1;
    }
    
    #controls Button {
        margin: 0 1;
        min-width: 10;
        width: auto;
        height: auto;
        padding: 0 1;
        color: $text;
        align: center middle;
    }
    
    #tick-btn {
        background: $success;
        color: $text;
    }
    
    #refresh-btn {
        background: $warning;  
        color: $text;
    }
    
    #identities-container {
        column-span: 1;
        row-span: 2;
        layout: grid;
        grid-size: 2 2;
        grid-gutter: 1;
    }
    
    #identity1, #identity2, #identity3, #identity4 {
        border: solid blue;
        overflow-y: auto;
    }
    
    #state-inspector {
        column-span: 1;
        row-span: 1;
        border: solid magenta;
        overflow-y: auto;
    }
    
    #event-log {
        column-span: 1;
        row-span: 1;
        border: solid green;
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
        ("ctrl+t", "tick", "Tick"),
        ("ctrl+r", "refresh", "Refresh"),
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
        
        # Set up SQL database path
        self.db_path = 'demo.db'
        os.environ['API_DB_PATH'] = self.db_path
        
        # Reset database on startup if requested
        if self.RESET_DB and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception as e:
                pass
        
        self.state_changes = []
        self._widget_counter = 0  # Counter for unique widget IDs
        self.last_invite_links = {}  # Store invite links by identity
        self.identity_mapping = {}  # Map pubkey to original identity parameter
        
        # Timer for auto-tick
        self.tick_timer = None
        self.is_playing = False
        
        # Event collector for real-time event display
        self.collected_events = []  # List of events as they happen
        self.event_counter = 0
        
        # Monkey-patch execute_api to collect events
        self._setup_event_collection()
    
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        # Removed Header() - we have our own controls
        
        # Control bar at the top - ensure all buttons are visible
        with Horizontal(id="controls"):
            yield Button("▶️ Play", id="play-pause-btn", variant="primary")
            yield Button("⏯️ Tick", id="tick-btn", variant="success")
            yield Button("🔄 Refresh", id="refresh-btn", variant="warning")
        
        # Left side - 4 identity panels in a 2x2 grid
        with Container(id="identities-container"):
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
        
        # Right side top - State inspector
        with VerticalScroll(id="state-inspector"):
            yield Label("State Inspector", classes="identity-label")
            yield RichLog(id="inspector-log", wrap=True, markup=True)
        
        # Right side bottom - Event log
        with VerticalScroll(id="event-log"):
            yield Label("Event Log (newest first)", classes="identity-label")
            yield RichLog(id="event-log-display", wrap=True, markup=True)
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when app starts."""
        # Initialize with empty state
        self.refresh_state()
        self.update_displays()
        self.update_event_log()
        
        # Load existing identities if not resetting
        if not self.RESET_DB:
            self.load_existing_identities()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        button_id = event.button.id
        
        if button_id == "play-pause-btn":
            self.toggle_play_pause()
        elif button_id == "tick-btn":
            self.action_tick()
        elif button_id == "refresh-btn":
            self.refresh_state()
            self.update_displays()
            self.update_event_log()
    
    def toggle_play_pause(self) -> None:
        """Toggle between play and pause states"""
        self.is_playing = not self.is_playing
        play_btn = self.query_one("#play-pause-btn", Button)
        
        if self.is_playing:
            play_btn.label = "⏸️ Pause"
            # Start the timer
            self.tick_timer = self.set_interval(1.0, self.auto_tick)
        else:
            play_btn.label = "▶️ Play"
            # Stop the timer
            if self.tick_timer:
                self.tick_timer.stop()
                self.tick_timer = None
    
    def auto_tick(self) -> None:
        """Called by timer when playing"""
        self.action_tick()
    
    def action_refresh(self) -> None:
        """Handle refresh action from keyboard shortcut"""
        self.refresh_state()
        self.update_displays()
        self.update_event_log()
    
    def load_existing_identities(self):
        """Load existing identities from database on startup."""
        try:
            # Get current identities
            identities = self.get_identities()
            
            if identities:
                # Log that we loaded existing data
                self.record_change(f"Loaded {len(identities)} existing identities", {}, {"identities": identities})
                
                # Assign first 4 identities to panels
                for i, identity in enumerate(identities[:4]):
                    panel_num = i + 1
                    setattr(self, f"identity{panel_num}_selected", i)

                    try:
                        label = self.query_one(f"#identity{panel_num}-dropdown", Static)
                        label.update(f"Identity {panel_num}: {identity.get('name', 'Unknown')}")
                    except Exception:
                        pass
                        pass
                    
        except Exception as e:
            self.record_change(f"Error loading identities: {e}", {}, {})
    
    def refresh_state(self):
        """Fetch current state from the database via API calls"""
        try:
            # Get identities via the list API
            response = execute_api(
                "message_via_tor",
                "GET",
                "/identities",
                data={}
            )
            
            if response.get("status") == 200:
                identities = response["body"].get("identities", [])
                
                # For state inspector, also show actual database state
                from core.db import create_db
                db = create_db(self.db_path)
                
                # Build complete state structure for inspector
                self.current_state = {
                    'state': {
                        'identities': identities,
                        'peers': db.get('state', {}).get('peers', []),
                        'messages': db.get('state', {}).get('messages', []),
                        'outgoing': db.get('state', {}).get('outgoing', [])
                    },
                    'eventStore': db.get('eventStore', [])[-10:]  # Last 10 events
                }
            else:
                self.current_state = {'state': {'identities': []}, 'eventStore': []}
        except Exception as e:
            self.current_state = {'state': {'identities': []}, 'eventStore': []}
    
    def get_identities(self):
        """Get list of identities from current state"""
        identities = []
        state = self.current_state.get('state', {})
        
        # Get identities from API response format
        identity_data = state.get('identities', [])
        if isinstance(identity_data, list):
            for item in identity_data:
                # API returns identityId and publicKey
                identities.append({
                    'id': item.get('identityId', 'unknown'),
                    'name': item.get('name', item.get('identityId', 'Unknown')[:8]),  # Use first 8 chars of ID if no name
                    'pubkey': item.get('publicKey', item.get('identityId', 'unknown'))
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
                data={}
            )
            
            if response.get("status") == 200:
                # Return success flag and messages from the API response
                return True, response.get("body", {}).get("messages", [])
            else:
                return False, []
        except Exception as e:
            return False, []
    
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
                success, messages = self.get_messages_for_identity(identity['pubkey'])
                # Only clear and rewrite the log when we have a successful response.
                # If the API call failed, preserve the existing log to avoid erasing messages.
                if success:
                    messages_log.clear()
                
                # Create a mapping of pubkeys to names for better display
                pubkey_to_name = {}
                for id_info in identities:
                    pubkey_to_name[id_info['pubkey']] = id_info['name']
                
                    for msg in messages:
                    sender_pubkey = msg.get('sender', 'Unknown')
                    sender_name = pubkey_to_name.get(sender_pubkey, sender_pubkey[:8] + '...')
                    text = msg.get('text', '')
                    
                    # Show if it's our own message
                    if sender_pubkey == identity['pubkey']:
                        messages_log.write(f"[bold cyan]{sender_name} (You):[/bold cyan] {text}")
                    else:
                        messages_log.write(f"[green]{sender_name}:[/green] {text}")
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
        state_json = json.dumps(self.current_state.get('state', {}), indent=2)
        inspector.write(state_json)
        
        # Also update event log
        self.update_event_log()
    
    def _setup_event_collection(self):
        """Set up event collection by wrapping execute_api"""
        demo_instance = self
        
        def execute_api_with_collection(protocol, method, path, data=None, params=None):
            """Wrapped version of execute_api that collects events"""
            # Call original API - pass all parameters
            response = original_execute_api(protocol, method, path, data, params)
            
            # Collect events from response
            if response.get('status') in [200, 201]:
                body = response.get('body', {})
                
                # Check for newEvents in response (from commands)
                if 'newEvents' in body:
                    for event in body['newEvents']:
                        demo_instance._collect_event(event, 'command', path)
                
                # For tick operations, collect job information
                if path == '/tick' and 'jobsRun' in body:
                    demo_instance._collect_event({
                        'type': 'tick',
                        'jobsRun': body.get('jobsRun', 0),
                        'eventsProcessed': body.get('eventsProcessed', 0)
                    }, 'system', path)
            
            return response
        
        import core.api
        core.api.execute_api = execute_api_with_collection
        globals()['execute_api'] = execute_api_with_collection
    
    def _collect_event(self, event, source, operation):
        """Collect an event for display"""
        self.event_counter += 1
        self.collected_events.append({
            'id': self.event_counter,
            'timestamp': time.time(),
            'source': source,
            'operation': operation,
            'event': event
        })
        
        # Keep only last 100 events in memory
        if len(self.collected_events) > 100:
            self.collected_events = self.collected_events[-100:]
        
        # Update display immediately
        self.call_later(self.update_event_log_display)
    
    def update_event_log_display(self):
        """Update just the event log display with collected events"""
        try:
            event_log = self.query_one("#event-log-display", RichLog)
            event_log.clear()
            
            # Also show events from the database event store for completeness
            from core.db import create_db
            db = create_db(self.db_path)
            db_events = db.get('eventStore', [])
            
            # Combine collected events with a sample of recent DB events
            all_events = []
            
            # Add collected events (from API responses)
            for event_info in self.collected_events:
                all_events.append({
                    'source': 'api',
                    'info': event_info
                })
            
            # Add recent DB events (last 20)
            for envelope in db_events[-20:]:
                all_events.append({
                    'source': 'db',
                    'envelope': envelope
                })
            
            # Sort by timestamp/id and show newest first
            all_events.sort(key=lambda x: x.get('info', {}).get('id', 0) if x['source'] == 'api' else 0, reverse=True)
            
            # Show events in reverse order (newest first)
            for item in all_events[:50]:  # Show last 50
                if item['source'] == 'api':
                    # Show collected event from API
                    event_info = item['info']
                    event_log.write(Text(f"\n[Event #{event_info['id']} - API/{event_info['source']}]", style="bold yellow"))
                    event_log.write(f"Operation: {event_info['operation']}")
                    
                    event = event_info['event']
                    event_type = event.get('type', 'unknown')
                    event_log.write(Text(f"Type: {event_type}", style="cyan"))
                    
                    # Show key fields based on event type
                    if event_type == 'message':
                        event_log.write(f"  Text: {event.get('text', 'N/A')[:50]}...")
                        event_log.write(f"  Sender: {event.get('sender', 'N/A')[:20]}...")
                    elif event_type == 'peer':
                        event_log.write(f"  Pubkey: {event.get('pubkey', 'N/A')[:20]}...")
                        event_log.write(f"  Name: {event.get('name', 'N/A')}")
                    elif event_type == 'identity':
                        event_log.write(f"  Pubkey: {event.get('pubkey', 'N/A')[:20]}...")
                        event_log.write(f"  Name: {event.get('name', 'N/A')}")
                    elif event_type == 'tick':
                        event_log.write(f"  Jobs run: {event.get('jobsRun', 0)}")
                        event_log.write(f"  Events processed: {event.get('eventsProcessed', 0)}")
                else:
                    # Show event from database
                    envelope = item['envelope']
                    metadata = envelope.get('metadata', {})
                    data = envelope.get('data', {})
                    
                    event_id = metadata.get('eventId', 'no-id')
                    event_id_display = event_id[:8] + '...' if event_id != 'no-id' else 'no-id'
                    event_log.write(Text(f"\n[Event from DB - {event_id_display}]", style="bold green"))
                    event_log.write(f"Type: {data.get('type', 'unknown')}")
                    event_log.write(f"Received by: {metadata.get('received_by', 'N/A')[:20]}...")
                    event_log.write(f"Self-generated: {metadata.get('selfGenerated', False)}")
                    
                    # Show event-specific data
                    if data.get('type') == 'message':
                        event_log.write(f"  Text: {data.get('text', 'N/A')[:50]}...")
                    elif data.get('type') == 'peer':
                        event_log.write(f"  Name: {data.get('name', 'N/A')}")
                
        except Exception as e:
            pass  # Silently ignore errors
    
    def update_event_log(self):
        """Update the event log display - now just calls the display update"""
        self.update_event_log_display()
    
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
        before_state = copy.deepcopy(self.current_state.get('state', {}))
        
        try:
            response = execute_api(
                "message_via_tor",
                "POST", 
                "/messages",
                data={
                    "text": text,
                    "senderId": identity['pubkey'],
                    # No db needed - using persistent database
                }
            )
            
            if response.get("status") == 201:
                # Refresh state to see the changes
                self.refresh_state()
                after_state = copy.deepcopy(self.current_state.get('state', {}))
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
        before_state = copy.deepcopy(self.current_state.get('state', {}))
        
        try:
            response = execute_api(
                "message_via_tor",
                "POST",
                "/tick",
                data={}
            )
            
            if response.get("status") == 200:
                # Refresh state to see the changes
                self.refresh_state()
                after_state = copy.deepcopy(self.current_state.get('state', {}))
                self.record_change("tick", before_state, after_state)
                self.update_displays()
        except Exception as e:
            self.record_change(f"tick ERROR: {str(e)}", before_state, before_state)
            self.update_displays()
    
    # Reset action removed - database resets on startup
    
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
            response = await self.create_identity(identity_num, args)
            if response.get('status') == 201:
                # Show success and identity info
                body = response.get('body', {})
                messages_log.write(f"[green]Identity created successfully![/green]")
                messages_log.write(f"[cyan]Identity ID: {body.get('identityId', 'N/A')[:32]}...[/cyan]")
                messages_log.write(f"[cyan]Name: {args}[/cyan]")
            else:
                messages_log.write(f"[red]Failed - Status: {response.get('status')}[/red]")
                messages_log.write(f"[red]Error: {response.get('body', {}).get('error', 'Unknown error')}[/red]")
            
        elif cmd == "/invite":
            # Generate an invite link for current identity
            identity_selected = getattr(self, f"identity{identity_num}_selected")
            identities = self.get_identities()
            
            messages_log.write(f"[dim]Debug: Panel {identity_num} selected index: {identity_selected}, total identities: {len(identities)}[/dim]")
            
            if identity_selected < 0:
                messages_log.write("[red]No identity selected. Create an identity first with /create <name>[/red]")
                return
            if identity_selected >= len(identities):
                messages_log.write(f"[red]Invalid selection: index {identity_selected} but only {len(identities)} identities exist[/red]")
                messages_log.write("[yellow]Try /refresh to update the identity list[/yellow]")
                return
            identity = identities[identity_selected]
            messages_log.write(f"[dim]Using identity: {identity['name']} (pubkey: {identity['pubkey'][:16]}...)[/dim]")
            # Generate invite link using the invite API
            try:
                response = execute_api(
                    "message_via_tor",
                    "POST",
                    f"/identities/{identity['pubkey']}/invite",
                    data={}
                )
                
                if response.get("status") in [200, 201]:
                    # Look for inviteLink (API now converts to camelCase)
                    invite_link = response["body"].get("inviteLink")
                    if not invite_link:
                        messages_log.write(f"[red]Error: No invite link in response[/red]")
                        messages_log.write(f"[dim]Response: {json.dumps(response.get('body', {}), indent=2)}[/dim]")
                        return
                    
                    # Store the link for this identity
                    self.last_invite_links[identity['pubkey']] = invite_link
                    
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
            
            if identity['pubkey'] in self.last_invite_links:
                invite_link = self.last_invite_links[identity['pubkey']]
                
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
                
        elif cmd == "/refresh":
            # Manually refresh state
            messages_log.write("[yellow]Refreshing state...[/yellow]")
            self.refresh_state()
            self.update_displays()
            messages_log.write("[green]State refreshed![/green]")
            
        elif cmd == "/debug":
            # Show debug information about current state
            messages_log.write("[bold cyan]Debug Information:[/bold cyan]")
            messages_log.write("")
            
            # Show current identity selection
            identity_selected = getattr(self, f"identity{identity_num}_selected")
            messages_log.write(f"[yellow]Panel {identity_num} selected index: {identity_selected}[/yellow]")
            
            # Show all identities
            identities = self.get_identities()
            messages_log.write(f"[yellow]Total identities: {len(identities)}[/yellow]")
            for i, identity in enumerate(identities):
                messages_log.write(f"  [{i}] name={identity['name']}, pubkey={identity['pubkey'][:16]}...")
            
            # Show raw state
            messages_log.write("")
            messages_log.write("[yellow]Raw current_state:[/yellow]")
            messages_log.write(json.dumps(self.current_state, indent=2))
            
        elif cmd == "/help":
            messages_log.write("[bold cyan]Available commands:[/bold cyan]")
            messages_log.write("")
            messages_log.write("[green]/create <name>[/green] - Create a new identity with the specified name")
            messages_log.write("[green]/invite[/green] - Generate an invite link to share with others")
            messages_log.write("[green]/link[/green] - Show the last generated invite link")
            messages_log.write("[green]/join <name> <invite-link>[/green] - Join a group using an invite link")
            messages_log.write("[green]/refresh[/green] - Manually refresh state from database")
            messages_log.write("[green]/debug[/green] - Show debug information about current state")
            messages_log.write("[green]/help[/green] - Show this help message")
            messages_log.write("")
            messages_log.write("[dim]Regular messages: Just type and press Enter to send[/dim]")
            messages_log.write("[dim]Navigation: Use Tab to switch between identities[/dim]")
            
        else:
            messages_log.write(f"[red]Unknown command: {cmd}[/red]")
            messages_log.write("Type /help for available commands")
    
    async def create_identity(self, identity_num: int, name: str) -> dict:
        """Create a new identity. Returns the API response."""
        before_state = copy.deepcopy(self.current_state.get('state', {}))
        
        try:
            response = execute_api(
                "message_via_tor",
                "POST",
                "/identities",
                data={
                    "name": name,
                    # No db needed - using persistent database
                }
            )
            
            if response.get("status") == 201:
                # Get the created identity ID from the response
                created_identity_id = response.get('body', {}).get('identityId')
                
                # Refresh state to see the changes
                self.refresh_state()
                after_state = copy.deepcopy(self.current_state.get('state', {}))
                self.record_change(f"identity.create: {name}", before_state, after_state)
                
                # Set this identity as selected for the panel
                identities = self.get_identities()
                
                # Debug output
                messages_log = self.query_one(f"#messages{identity_num}", RichLog)
                messages_log.write(f"[dim]Debug: Looking for ID {created_identity_id[:16]}...[/dim]")
                messages_log.write(f"[dim]Debug: Found {len(identities)} identities after refresh[/dim]")
                
                found = False
                for i, identity in enumerate(identities):
                    messages_log.write(f"[dim]  [{i}] id={identity['id'][:16]}... name={identity['name']}[/dim]")
                    # Match by ID instead of name since API might not return the name
                    if identity['id'] == created_identity_id or identity['pubkey'] == created_identity_id:
                        setattr(self, f"identity{identity_num}_selected", i)
                        messages_log.write(f"[dim]  ^^ Selected this one![/dim]")
                        found = True
                        break
                
                if not found:
                    messages_log.write(f"[yellow]Warning: Created identity not found in list![/yellow]")
                
                self.update_displays()
            
            return response
                
        except Exception as e:
            self.record_change(f"identity.create ERROR: {str(e)}", before_state, before_state)
            self.update_displays()
            return {"status": 500, "body": {"error": str(e)}}
    
    async def join_with_invite(self, identity_num: int, name: str, invite_link: str) -> bool:
        """Join using an invite link."""
        messages_log = self.query_one(f"#messages{identity_num}", RichLog)
        
        # First check if we already have an identity in this slot
        identity_selected = getattr(self, f"identity{identity_num}_selected")
        if identity_selected >= 0:
            messages_log.write("[yellow]Identity already exists in this slot. Use an empty slot.[/yellow]")
            return False
            
        before_state = copy.deepcopy(self.current_state.get('state', {}))
        
        try:
            # Call the join API endpoint with the invite link and name
            response = execute_api(
                "message_via_tor",
                "POST",
                "/join",
                data={
                    "name": name,
                    "inviteLink": invite_link,
                    # No db needed - using persistent database
                }
            )
            
            if response.get("status") == 201:
                # Refresh state to see the changes
                self.refresh_state()
                after_state = copy.deepcopy(self.current_state.get('state', {}))
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
    import argparse
    parser = argparse.ArgumentParser(description='Message via Tor Demo')
    parser.add_argument('--no-reset', action='store_true', 
                      help='Do not reset database on startup (preserve state)')
    parser.add_argument('--db-path', default='demo.db',
                      help='Path to database file (default: demo.db)')
    args = parser.parse_args()
    
    # Configure the app based on CLI arguments
    MessageViaTorDemo.RESET_DB = not args.no_reset
    
    app = MessageViaTorDemo()
    app.db_path = args.db_path  # Override db path if specified
    app.run()