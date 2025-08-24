# test_textual.py
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input
from textual.containers import Vertical
from rich.panel import Panel

class RichTestApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }
    Vertical {
        width: 1fr;
        border: round white;
    }
    Static {
        height: 80%;
        content-align: center middle;
    }
    Input {
        height: 3;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "tick", "Tick"),
        ("1", "focus_input1", "Focus Input 1"),
        ("2", "focus_input2", "Focus Input 2"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static(Panel("Identity 1\nMessages here", title="Identity 1")),
            Input(placeholder="Message 1", id="input1")
        )
        yield Vertical(
            Static(Panel("Identity 2\nMessages here", title="Identity 2")),
            Input(placeholder="Message 2", id="input2")
        )
        yield Vertical(
            Static(Panel("State Changes\nLog here", title="State Changes")),
        )
        yield Footer()

    def action_tick(self):
        self.query_one("#input1").value = "Tick occurred!"

    def action_focus_input1(self):
        self.query_one("#input1").focus()

    def action_focus_input2(self):
        self.query_one("#input2").focus()

if __name__ == "__main__":
    try:
        app = RichTestApp()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()