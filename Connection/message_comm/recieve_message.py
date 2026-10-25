"""Receiving and decrypting messages delivered by the messenger server."""
import base64

from nacl.public import Box, PublicKey
from nacl.exceptions import CryptoError

from Connection.server_client import MessengerServerClient

class ReceiveMessage:
    def __init__(self, server_client=None):
        self.server_client = server_client or MessengerServerClient()

    def next_message(self, recipient_private_key, timeout=None):
        """Return ``[sender, plaintext, True]`` or a failed result/``None`` on timeout."""
        payload = self.server_client.receive_message(timeout)
        if payload is None:
            return None
        try:
            sender_response = self.server_client.public_key_for(payload["from"])
            if sender_response.get("type") == "error":
                return [sender_response["message"], False]
            sender_key = PublicKey(base64.b64decode(sender_response["public_key"], validate=True))
            plaintext = Box(recipient_private_key, sender_key).decrypt(
                base64.b64decode(payload["ciphertext"], validate=True)
            ).decode("utf-8")
            return [payload["from"], plaintext, True]
        except (CryptoError, KeyError, TypeError, ValueError, UnicodeDecodeError):
            return ["Could not decrypt the received message.", False]


# Preserve the misspelled module's former public class name for existing imports.
SendMessage = ReceiveMessage

        
        
