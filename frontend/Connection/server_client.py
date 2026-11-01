"""Synchronous client for the messenger WebSocket server.

The GUI is synchronous (Tkinter), so this small adapter deliberately uses the
sync API exposed by ``websockets`` rather than making UI callers manage an
asyncio event loop. Keep one instance alive after login so it can receive live
messages as well as messages queued by the server while the user was offline.
"""
import json
import os

from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

load_dotenv()


class ServerConnectionError(ConnectionError):
    """The messenger server could not be reached or closed the connection."""


class MessengerServerClient:
    def __init__(self, url=None):
        self.url = url or os.getenv("MESSENGER_SERVER_URL", "ws://localhost:8765")
        self._socket = None
        self._pending_messages = []

    @property
    def connected(self):
        return self._socket is not None

    def open(self):
        if self._socket is None:
            try:
                self._socket = connect(self.url, open_timeout=10)
            except OSError as exc:
                raise ServerConnectionError(
                    f"Could not connect to the messenger server at {self.url}."
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

        while True:
            response = self._receive()
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
            return self._pending_messages.pop(0)
        try:
            while True:
                response = self._receive(timeout)
                if response.get("type") == "new_message":
                    return response
                if response.get("type") == "error":
                    raise ServerConnectionError(response.get("message", "Server error."))
        except TimeoutError:
            return None
