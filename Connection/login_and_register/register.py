import base64
from Connection.login_and_register.key_generator import GenerateKey
from Connection.server_client import MessengerServerClient

class UserLoginRegister:
    def __init__(self, server_client=None):
        self.server_client = server_client or MessengerServerClient()
        self.key_generator = GenerateKey()
        self.username = None
        self.private_key = None

    def register_user(self, username, password):
        public_key = base64.b64encode(bytes(self.key_generator.public_key)).decode('ascii')
        response = self.server_client.register(username, password, public_key)
        if response.get("type") != "ok":
            return [response.get("message", "Registration failed."), False]

        self.username = response["user"]
        self.private_key = self.key_generator.private_key
        self.key_generator.save_private_key(password, self.username)
        return [f"Successfully registered '{self.username}'", True]
