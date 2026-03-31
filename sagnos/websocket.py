"""
sagnos/websocket.py
Re-exports stream from core.
WebSocket handling is inside server.py.
"""

from .core import stream, get_streams

__all__ = ["stream", "get_streams"]