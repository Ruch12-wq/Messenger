"""Synchronous client for the messenger WebSocket server.

The GUI is synchronous (Tkinter), so this small adapter deliberately uses the
sync API exposed by ``websockets`` rather than making UI callers manage an
asyncio event loop. Keep one instance alive after login so it can receive live
messages as well as messages queued by the server while the user was offline.
"""
import json
import os
import time
from collections import deque
from pathlib import Path

from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidURI
from websockets.sync.client import connect

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class ServerConnectionError(ConnectionError):
    """The messenger server could not be reached or closed the connection."""


class MessengerServerClient:
    def __init__(self, url=None):
        self.url = (url or os.getenv("MESSENGER_SERVER_URL") or "ws://localhost:8765").strip()
        self._socket = None
        self._pending_messages = deque()

    @property
    def connected(self):
        return self._socket is not None

    def open(self):
        if self._socket is None:
            try:
                self._socket = connect(self.url, open_timeout=10)
            except (OSError, InvalidHandshake, InvalidURI) as exc:
                raise ServerConnectionError(
                    f"Cannot connect to {self.url}. Check the server address and network. "
                    "On another laptop, localhost points to that laptop; use the server computer’s IP address."
                ) from exc
        return self

    def close(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def _receive(self, timeout=None):
        self.open()
        try:
            raw = self._socket.recv(timeout=timeout)
            return json.loads(raw)
        except TimeoutError:
            # A zero-timeout UI poll simply means no message has arrived yet.
            # TimeoutError is an OSError subclass, so handle it before the
            # connection-error branch below.
            raise
        except (ConnectionClosed, OSError, json.JSONDecodeError) as exc:
            self.close()
            raise ServerConnectionError("The messenger server connection was closed.") from exc

    def request(self, payload):
        """Send a request and return its response, queueing incoming messages."""
        self.open()
        try:
            self._socket.send(json.dumps(payload))
        except (ConnectionClosed, OSError) as exc:
            self.close()
            raise ServerConnectionError("The messenger server connection was closed.") from exc

        deadline = time.monotonic() + 15
        while True:
            try:
                response = self._receive(max(0, deadline - time.monotonic()))
            except TimeoutError as exc:
                self.close()
                raise ServerConnectionError("The server did not respond within 15 seconds. Try again.") from exc
            if response.get("type") == "new_message":
                self._pending_messages.append(response)
                continue
            return response

    def register(self, username, login_secret, public_key):
        return self.request({
            "type": "register", "user": username,
            "login_secret": login_secret, "public_key": public_key,
        })

    def login(self, username, login_secret):
        return self.request({
            "type": "login", "user": username,
            "login_secret": login_secret,
        })

    def public_key_for(self, username):
        return self.request({"type": "get_key", "user": username})

    def send_ciphertext(self, recipient, ciphertext):
        return self.request({"type": "send", "to": recipient, "ciphertext": ciphertext})

    def receive_message(self, timeout=None):
        """Return the next server-delivered encrypted message, or ``None`` on timeout."""
        if self._pending_messages:
            return self._pending_messages.popleft()
        try:
            while True:
                response = self._receive(timeout)
                if response.get("type") == "new_message":
                    return response
                if response.get("type") == "error":
                    raise ServerConnectionError(response.get("message", "Server error."))
        except TimeoutError:
            return None
