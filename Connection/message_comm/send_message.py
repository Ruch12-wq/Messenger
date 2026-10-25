"""End-to-end encrypted message sending through the messenger server."""
import base64

from nacl.public import Box, PublicKey

from Connection.server_client import MessengerServerClient

class SendMessage:
    def __init__(self, server_client=None):
        self.server_client = server_client or MessengerServerClient()

    def message_to_db(self, sender, recipient, message):
        """Compatibility name; messages now go to the server, never MongoDB directly."""
        key_response = self.server_client.public_key_for(recipient)
        if key_response.get("type") == "error":
            return [key_response["message"], False]

        try:
            recipient_key = PublicKey(base64.b64decode(key_response["public_key"], validate=True))
            ciphertext = Box(sender.private_key, recipient_key).encrypt(message.encode("utf-8"))
        except (AttributeError, KeyError, TypeError, ValueError):
            return ["Could not encrypt the message for that recipient.", False]

        response = self.server_client.send_ciphertext(
            recipient, base64.b64encode(ciphertext).decode("ascii")
        )
        if response.get("type") == "sent":
            return [f"Message sent to '{recipient}'", True]
        return [response.get("message", "The server could not send the message."), False]
