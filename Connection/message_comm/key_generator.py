from dotenv import load_dotenv
import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import bcrypt
from nacl.public import PrivateKey
import nacl.pwhash, nacl.secret, nacl.utils

class GenerateKey:
    def __init__(self):
        self.private_key = PrivateKey.generate()
        self.public_key = self.private_key.public_key

    def save_private_key(self, password: str, filename: str):
        path = f"{filename}.key"
        salt = nacl.utils.random(nacl.pwhash.argon2id.SALTBYTES)
        k = nacl.pwhash.argon2id.kdf(nacl.secret.SecretBox.KEY_SIZE, password.encode(), salt)

        encrypted = nacl.secret.SecretBox(k).encrypt(bytes(self.private_key))

        with open(path, 'wb') as f:
            f.write(salt + encrypted)
