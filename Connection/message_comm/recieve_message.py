from dotenv import load_dotenv
import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from nacl.public import Box

class SendMessage:
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
        collection_name = self._required_env("MONGO_COLLECTION_MESSAGES")
        self.mongo_collection = self.client[self.mongo_db][collection_name]


    @staticmethod
    def _required_env(name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value

    def ping_messages(self, sender, recipient):
        sender_data = self.client[self.mongo_db][self._required_env("MONGO_COLLECTION_USERS")].find_one({"username": sender})
        if not sender_data:
            return [f"Sender '{sender}' does not exist", False]

        messages_ping = self.mongo