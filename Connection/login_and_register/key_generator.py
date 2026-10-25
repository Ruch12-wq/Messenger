
from pathlib import Path

from nacl.public import PrivateKey
import nacl.pwhash, nacl.secret, nacl.utils

class GenerateKey:
    def __init__(self):
        self.private_key = PrivateKey.generate()
        self.public_key = self.private_key.public_key

    def save_private_key(self, password: str, filename: str):
        path = Path(f"{filename}.key")
        salt = nacl.utils.random(nacl.pwhash.argon2id.SALTBYTES)
        k = nacl.pwhash.argon2id.kdf(nacl.secret.SecretBox.KEY_SIZE, password.encode(), salt)

        encrypted = nacl.secret.SecretBox(k).encrypt(bytes(self.private_key))

        with path.open('wb') as f:
            f.write(salt + encrypted)

    @staticmethod
    def load_private_key(password: str, filename: str) -> PrivateKey:
        """Load a private key saved by :meth:`save_private_key`."""
        payload = Path(f"{filename}.key").read_bytes()
        salt_size = nacl.pwhash.argon2id.SALTBYTES
        if len(payload) <= salt_size:
            raise ValueError("Invalid private-key file.")
        salt, encrypted = payload[:salt_size], payload[salt_size:]
        key = nacl.pwhash.argon2id.kdf(
            nacl.secret.SecretBox.KEY_SIZE, password.encode(), salt
        )
        try:
            return PrivateKey(nacl.secret.SecretBox(key).decrypt(encrypted))
        except Exception as exc:
            raise ValueError("Could not decrypt the private key.") from exc
