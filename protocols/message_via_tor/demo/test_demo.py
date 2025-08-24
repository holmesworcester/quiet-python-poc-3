#!/usr/bin/env python3
"""
Tests for the message_via_tor Textual demo.
"""

import pytest
from textual.pilot import Pilot
from demo_textual import MessageViaTorDemo


@pytest.mark.asyncio
async def test_app_starts():
    """Test that the app starts and has the expected widgets."""
    app = MessageViaTorDemo()
    async with app.run_test() as pilot:
        # Check header exists
        assert app.query_one("Header")
        
        # Check all panels exist
        assert app.query_one("#test-list")
        assert app.query_one("#identity1")
        assert app.query_one("#identity2")
        assert app.query_one("#state-changes")
        assert app.query_one("#state-inspector")
        
        # Check input fields
        assert app.query_one("#input1")
        assert app.query_one("#input2")


@pytest.mark.asyncio
async def test_default_test_loaded():
    """Test that test #12 is loaded by default with Alice identity."""
    app = MessageViaTorDemo()
    async with app.run_test() as pilot:
        # Check that Alice is shown in identity 1
        identity_label = app.query_one("#identity1 Label")
        assert "Alice" in identity_label.renderable


@pytest.mark.asyncio
async def test_create_identity():
    """Test creating a new identity."""
    app = MessageViaTorDemo()
    async with app.run_test() as pilot:
        # Get initial identity count
        initial_identities = len(app.get_identities())
        
        # Press 'i' to create identity
        await pilot.press("i")
        
        # Check identity was created
        new_identities = len(app.get_identities())
        assert new_identities > initial_identities
        
        # Check state change was recorded
        assert len(app.state_changes) > 0
        assert "identity.create" in app.state_changes[-1]['operation']


@pytest.mark.asyncio
async def test_send_message():
    """Test sending a message from identity 1."""
    app = MessageViaTorDemo()
    async with app.run_test() as pilot:
        # Focus input1
        await pilot.click("#input1")
        
        # Type a message
        await pilot.press("H", "e", "l", "l", "o")
        
        # Submit with Enter
        await pilot.press("enter")
        
        # Check message was sent (state change recorded)
        assert any("message:" in change['operation'] for change in app.state_changes)
        
        # Check input was cleared
        input1 = app.query_one("#input1")
        assert input1.value == ""


@pytest.mark.asyncio
async def test_tick():
    """Test running a tick cycle."""
    app = MessageViaTorDemo()
    async with app.run_test() as pilot:
        # Press 't' to tick
        await pilot.press("t")
        
        # Check tick was recorded in state changes
        assert any("tick" in change['operation'] for change in app.state_changes)


@pytest.mark.asyncio
async def test_reset():
    """Test resetting the state."""
    app = MessageViaTorDemo()
    async with app.run_test() as pilot:
        # Create some state changes first
        await pilot.press("i")  # Create identity
        
        # Reset
        await pilot.press("r")
        
        # Check state was reset
        assert len(app.get_identities()) == 0
        assert any("reset" in change['operation'] for change in app.state_changes)


@pytest.mark.asyncio  
async def test_state_inspector():
    """Test that state inspector shows changes."""
    app = MessageViaTorDemo()
    async with app.run_test() as pilot:
        # Create an identity to generate a state change
        await pilot.press("i")
        
        # Check inspector shows before/after
        inspector_log = app.query_one("#inspector-log")
        content = inspector_log.lines
        
        # Should have BEFORE and AFTER sections
        assert any("BEFORE:" in str(line) for line in content)
        assert any("AFTER:" in str(line) for line in content)


if __name__ == "__main__":
    pytest.main([__file__])