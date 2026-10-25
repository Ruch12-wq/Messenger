from Connection.server_client import MessengerServerClient
from Connection.login_and_register.key_generator import GenerateKey

class UserLogin:
    def __init__(self, server_client=None):
        self.server_client = server_client or MessengerServerClient()
        self.username = None
        self.private_key = None
    
    def login_user(self, username, password):
        response = self.server_client.login(username, password)
        if response.get("type") != "ok":
            return [response.get("message", "User login failed."), False]

        self.username = response["user"]
        try:
            self.private_key = GenerateKey.load_private_key(password, self.username)
        except (OSError, ValueError):
            # Authentication may still succeed on a different device; receiving
            # encrypted messages requires importing that device's private key.
            self.private_key = None
        return ["User login successful", True]
