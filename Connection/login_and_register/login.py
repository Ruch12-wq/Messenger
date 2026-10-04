from dotenv import load_dotenv
import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import bcrypt

class UserLogin:
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

    @staticmethod
    def _required_env(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value
    
    def login_user(self, username, password):
        user = self.mongo_collection.find_one({"username": username})
        if not user:
            return [f"User '{username}' does not exist", False]

        if bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            return ["User login successful", True]
        else:
            return ["User password incorrect", False]