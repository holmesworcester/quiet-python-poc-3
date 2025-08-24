# Message via Tor Demo Client Plan

## Overview

A simple terminal testing tool for the message_via_tor protocol. Shows two identities side-by-side, lets you send group messages, and displays state changes like a Redux debugger.

## UI Layout

```
┌──────────────┬─────────────┬─────────────┬─────────────┬──────────────────────┐
│Test Selector │ Identity 1  │ Identity 2  │State Changes│   State Inspector    │
├──────────────┼─────────────┼─────────────┼─────────────┼──────────────────────┤
│• Create ID   │┌─Alice ──▼─┐│┌─Bob ────▼─┐│>msg.create  │ BEFORE:              │
│• Send msg    │└───────────┘│└───────────┘│ +msg:"Hi"   │ messages: []         │
│• Unknown peer│             │             │>tick        │ outgoing: []         │
│> Full sync   │Alice: Hi!   │Alice: Hi!   │ +outgoing:2 │                      │
│              │Bob: Hey     │Bob: Hey     │>incoming    │ AFTER:               │
│[Space: Load] │Charlie: Yo  │Charlie: Yo  │ -outgoing:2 │ messages: [          │
│[R: Reset]    │             │             │ +messages:2 │   {text:"Hi",        │
│              │[__________] │[__________] │>peer.create │    sender:"alice"}   │
│              │             │             │ +peer:char  │ ]                    │
│              │             │             │             │ outgoing: []         │
└──────────────┴─────────────┴─────────────┴─────────────┴──────────────────────┘
[Space: Load Test] [R: Reset] [T: Tick] [Q: Quit] [Click change to inspect]
```

## Implementation

### Single File: `demo.py`

All functionality in one file to keep it simple:

1. **Test Loading**
   - Parse handler JSON files on startup
   - Extract test descriptions and states
   - Load selected test's `given` state

2. **State Management**
   - Single state dict matching protocol structure
   - Track state changes for debug panel
   - Direct function calls to handler commands

3. **UI Components**
   - Test list (left panel)
   - Two identity panels with dropdown and messages
   - State change log (middle-right panel)
   - State inspector (far-right panel)
   - Message input fields (Enter to send)

4. **Manual Tick**
   - Press 'T' to run one tick cycle
   - Executes sync_peers and tor_simulator
   - Updates UI with results

## Key Simplifications

- No automatic polling - manual tick only
- Messages broadcast to all peers (no recipient selection)
- Two identities visible at once (dropdown to switch which)
- All state changes logged to debug panel
- Single file implementation
- No modular architecture needed

## Libraries

- `rich` for terminal UI (panels, inputs, live updates)
- Standard library for everything else

## Features

- Load any test as starting state
- Send messages from either identity
- See all messages in both identity views
- Manual tick to trigger sync/delivery
- State change log shows what's happening
- State inspector shows before/after for selected change
- Click on any state change to see detailed diff
- Reset to clear state