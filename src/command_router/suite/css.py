#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


style = """
Screen {
    background: $surface;
    color: $text;
}

#command-input {
    margin: 1 2 0 2;
}

#status {
    height: 1;
    margin: 1 2 0 2;
    text-style: bold;
}

#status.status-ok {
    color: $success;
}

#status.status-error {
    color: $error;
}

#status.status-info {
    color: $text-muted;
}

#sugg {
    height: 2;
    margin: 0 2;
    color: $text-muted;
    overflow-x: hidden;
}

#context {
    height: 2;
    margin: 0 2 1 2;
    color: $accent;
    text-style: bold;
}

#output-windows {
    width: 100%;
    height: 1fr;
    min-height: 8;
    padding: 0 2;
}

.window {
    width: 1fr;
    height: 100%;
    min-width: 0;
    border: round $primary;
    padding: 0 1;
}

#result-window {
    margin-right: 1;
}

.window-title {
    height: 2;
    padding: 0 1;
    color: $accent;
    text-style: bold;
}

.window-content {
    width: 100%;
    height: 1fr;
    min-width: 0;
}

#size-warning {
    layer: warning;
    display: none;
    position: absolute;
    width: 100%;
    height: 100%;
    padding: 2 4;
    background: $surface;
    color: $warning;
    content-align: center middle;
    text-align: center;
    text-style: bold;
}

#size-warning.visible {
    display: block;
}
"""
