
from pathlib import Path

from nacl.public import PrivateKey
import nacl.pwhash, nacl.secret, nacl.utils

class GenerateKey:
    LOCAL_PREFIX = b"MESSENGER-LOCAL-2\n"

    @staticmethod
    def derive(password, salt):
        return nacl.pwhash.argon2id.kdf(
            32, password.encode(), salt,
            opslimit=nacl.pwhash.argon2id.OPSLIMIT_INTERACTIVE,
            memlimit=nacl.pwhash.argon2id.MEMLIMIT_INTERACTIVE)

    def __init__(self):
        self.private_key = PrivateKey.generate()
        self.public_key = self.private_key.public_key

    def save_private_key(self, password: str, filename: str):
        path = Path(f"{filename}.key")
        salt = nacl.utils.random(nacl.pwhash.argon2id.SALTBYTES)
        k = self.derive(password, salt)

        encrypted = nacl.secret.SecretBox(k).encrypt(bytes(self.private_key))

        self._write_private(path, self.LOCAL_PREFIX + salt + encrypted)

    @staticmethod
    def load_private_key(password: str, filename: str) -> PrivateKey:
        """Load a private key saved by :meth:`save_private_key`."""
        payload = Path(f"{filename}.key").read_bytes()
        modern = payload.startswith(GenerateKey.LOCAL_PREFIX)
        if modern:
            payload = payload[len(GenerateKey.LOCAL_PREFIX):]
        salt_size = nacl.pwhash.argon2id.SALTBYTES
        if len(payload) <= salt_size:
            raise ValueError("Invalid private-key file.")
        salt, encrypted = payload[:salt_size], payload[salt_size:]
        key = GenerateKey.derive(password, salt) if modern else nacl.pwhash.argon2id.kdf(
            nacl.secret.SecretBox.KEY_SIZE, password.encode(), salt
        )
        try:
            return PrivateKey(nacl.secret.SecretBox(key).decrypt(encrypted))
        except Exception as exc:
            raise ValueError("Could not decrypt the private key.") from exc

    @staticmethod
    def export_key(private_key, username, passphrase, destination):
        """Portable authenticated encryption; no plaintext key is written."""
        import base64
        import json
        if len(passphrase) < 16:
            raise ValueError("Пароль перенесення має містити щонайменше 16 символів.")
        salt = nacl.utils.random(nacl.pwhash.argon2id.SALTBYTES)
        key = GenerateKey.derive(passphrase, salt)
        payload = json.dumps({"version": 1, "username": username,
                              "key": base64.b64encode(bytes(private_key)).decode()}).encode()
        encrypted = nacl.secret.SecretBox(key).encrypt(payload)
        GenerateKey._write_private(Path(destination), b"MESSENGER-KEY-1\n" + salt + encrypted)

    @staticmethod
    def import_key(source, passphrase, username, expected_public_key, account_password):
        import base64
        import json
        if Path(source).stat().st_size > 4096:
            raise ValueError("Невідомий формат ключа.")
        payload = Path(source).read_bytes()
        prefix = b"MESSENGER-KEY-1\n"
        if not payload.startswith(prefix) or len(payload) > 4096:
            raise ValueError("Невідомий формат ключа.")
        body = payload[len(prefix):]
        salt_size = nacl.pwhash.argon2id.SALTBYTES
        try:
            key = GenerateKey.derive(passphrase, body[:salt_size])
            data = json.loads(nacl.secret.SecretBox(key).decrypt(body[salt_size:]))
            private = PrivateKey(base64.b64decode(data["key"], validate=True))
            if data["version"] != 1 or data["username"] != username or bytes(private.public_key) != base64.b64decode(expected_public_key):
                raise ValueError
        except Exception as exc:
            raise ValueError("Неправильний пароль, пошкоджений файл або ключ іншого користувача.") from exc
        generator = GenerateKey()
        generator.private_key = private
        generator.save_private_key(account_password, username)
        return private

    @staticmethod
    def _write_private(path, payload):
        import os
        import tempfile
        descriptor, temporary = tempfile.mkstemp(dir=path.resolve().parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
