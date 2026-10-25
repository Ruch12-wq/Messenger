import base64
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import bcrypt
from Connection.login_and_register.key_generator import GenerateKey

class UserLoginRegister:
    def __init__(self):
        load_dotenv()
        self.mongo_uri = self._required_env("MONGO_URI")
        self.client = MongoClient(self.mongo_uri, server_api=ServerApi('1'))

        try:
            self.client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as exc:
            raise ConnectionError(
                "Could not authenticate with MongoDB Atlas. Check MONGO_URI, "
                "the Atlas database user, and Network Access settings."
            ) from exc

        self.mongo_db = self._required_env("MONGO_DB")
        collection_name = self._required_env("MONGO_COLLECTION_USERS")
        self.mongo_collection = self.client[self.mongo_db][collection_name]
        self.key_generator = GenerateKey()

    @staticmethod
    def _required_env(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value

    def register_user(self, username, password):
        user_exists = self.mongo_collection.find_one({"username": username})
        if user_exists:
            return [f"User '{username}' already exists", False]

        self.key_generator.save_private_key(password, username)
        public_key = base64.b64encode(bytes(self.key_generator.public_key)).decode('ascii')

        user_data = {
            "username": username,
            "password": bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            "public_key": public_key
        }

        self.mongo_collection.insert_one(user_data)
        return [f"Successfully registered '{username}'", True]
