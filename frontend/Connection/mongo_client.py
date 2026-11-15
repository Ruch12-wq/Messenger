"""Direct encrypted messaging through a shared MongoDB database."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from bson import ObjectId
from collections import deque

import certifi
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError


def hash_secret(secret, salt):
    if hasattr(hashlib, "scrypt"):
        return hashlib.scrypt(secret.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    from nacl.bindings import crypto_pwhash_scryptsalsa208sha256_ll
    return crypto_pwhash_scryptsalsa208sha256_ll(secret.encode(), salt, 2**14, 8, 1, dklen=32)


class MongoMessengerClient:
    url = "mongodb"

    def __init__(self, uri=None):
        self.uri = uri or os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
        self.client = None
        self.user = None
        self.pending = deque()
        self.keys = {}
        self.next_poll = 0

    @property
    def connected(self):
        return self.client is not None

    def open(self):
        if self.client is not None:
            return self
        if not self.uri:
            raise ConnectionError("Set MONGO_URI in .env on this laptop.")
        try:
            options = dict(serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                           socketTimeoutMS=5000)
            if self.uri.lower().startswith("mongodb+srv://"):
                options["tlsCAFile"] = certifi.where()
            self.client = MongoClient(self.uri, **options)
            self.client.admin.command("ping")
            db = self.client[os.getenv("MONGO_DB") or os.getenv("MONGODB_DB", "Messenger")]
            self.users = db[os.getenv("MONGO_COLLECTION_USERS", "users_login")]
            self.messages = db[os.getenv("MONGO_COLLECTION_MESSAGES", "messages")]
            self.users.create_index("username", unique=True)
            self.messages.create_index([("recipient", 1), ("delivered", 1), ("time", 1)])
            self.messages.create_index([("sender", 1), ("updated_at", 1)])
            self.messages.create_index([("recipient", 1), ("updated_at", 1)])
        except (PyMongoError, ValueError):
            self.close()
            # Don't expose credentials embedded in a MongoDB URI.
            raise ConnectionError("Cannot connect to MongoDB. Check MONGO_URI, database permissions and Atlas Network Access.") from None
        return self

    def close(self):
        if self.client is not None:
            self.client.close()
        self.client = None
        self.user = None
        self.pending.clear()
        self.keys.clear()

    @staticmethod
    def error(message):
        return {"type": "error", "message": message}

    def register(self, username, login_secret, public_key):
        self.open()
        name = username.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,20}", name):
            return self.error("Username must be 3-20 characters: letters, digits, underscore.")
        if not 16 <= len(login_secret) <= 256:
            return self.error("Password must be 16-256 characters.")
        try:
            if len(base64.b64decode(public_key, validate=True)) != 32:
                raise ValueError
        except (ValueError, TypeError):
            return self.error("Invalid public key.")
        salt = secrets.token_bytes(16)
        record = dict(username=name, salt=salt.hex(),
                      hash=hash_secret(login_secret, salt).hex(), public_key=public_key)
        try:
            self.users.insert_one(record)
        except DuplicateKeyError:
            return self.error("That username is already taken.")
        self.user = name
        return {"type": "ok", "user": name, "action": "register"}

    def login(self, username, login_secret):
        self.open()
        self.user = None
        self.pending.clear()
        self.next_poll = 0
        name = username.strip().lower()
        if not 16 <= len(login_secret) <= 256:
            return self.error("Wrong username or password.")
        record = self.users.find_one({"username": name})
        salt = bytes.fromhex(record["salt"]) if record else bytes(16)
        hashed = hash_secret(login_secret, salt).hex()
        if not record or not hmac.compare_digest(hashed, record.get("hash", "")):
            return self.error("Wrong username or password.")
        self.user = name
        return {"type": "ok", "user": name, "action": "login"}

    def public_key_for(self, username):
        if not self.user:
            return self.error("Please log in first.")
        name = username.strip().lower()
        if name not in self.keys:
            record = self.users.find_one({"username": name}, {"public_key": 1})
            if not record:
                return self.error("No such user.")
            self.keys[name] = record["public_key"]
        return {"type": "key", "user": name, "public_key": self.keys[name]}

    def send_ciphertext(self, recipient, ciphertext, message_id=None):
        key = self.public_key_for(recipient)
        if key["type"] == "error":
            return key
        if not isinstance(ciphertext, str) or not ciphertext or len(ciphertext) > 200_000:
            return self.error("Invalid message.")
        message_id = message_id or str(uuid.uuid4())
        self.messages.update_one(
            {"_id": message_id},
            {"$setOnInsert": dict(sender=self.user, recipient=key["user"],
                                  ciphertext=ciphertext, time=time.time(), delivered=False, read=False),
             "$currentDate": {"updated_at": True}}, upsert=True)
        return {"type": "sent", "id": message_id, "delivered": False}

    def verify_password(self, password):
        record = self.users.find_one({"username": self.user})
        return bool(record and 16 <= len(password) <= 256 and hmac.compare_digest(
            hash_secret(password, bytes.fromhex(record["salt"])).hex(), record["hash"]))

    def history_updates(self, since=None):
        if not self.user:
            raise ConnectionError("Please log in first.")
        query = {"$or": [{"sender": self.user}, {"recipient": self.user}]}
        if since is not None:
            query = {"$and": [query, {"updated_at": {"$gte": since}}]}
        return list(self.messages.find(query).sort([("time", 1), ("_id", 1)]))

    def acknowledge(self, ids, read=False):
        identifiers = []
        for value in ids:
            identifiers.append(value)
            if ObjectId.is_valid(value):
                identifiers.append(ObjectId(value))
        fields = {"delivered": True}
        if read:
            fields["read"] = True
        self.messages.update_many(
            {"_id": {"$in": identifiers}, "recipient": self.user,
             ("read" if read else "delivered"): {"$ne": True}},
            {"$set": fields, "$currentDate": {"updated_at": True}})

    def receive_message(self, timeout=None):
        if not self.user:
            raise ConnectionError("Please log in first.")
        if self.pending:
            return self.pending.popleft()
        now = time.monotonic()
        if now < self.next_poll:
            time.sleep(min(timeout or 0, self.next_poll - now))
            return None
        self.next_poll = now + 0.5
        # Batch reads keep the number of database requests low when idle or busy.
        docs = list(self.messages.find({"recipient": self.user, "delivered": False})
                    .sort([("time", 1), ("_id", 1)]).limit(100))
        if docs:
            self.messages.update_many({"_id": {"$in": [d["_id"] for d in docs]}},
                                      {"$set": {"delivered": True}})
            self.pending.extend(dict(type="new_message", id=str(d["_id"]),
                                     **{"from": d["sender"]}, ciphertext=d["ciphertext"],
                                     time=d["time"]) for d in docs)
            return self.pending.popleft()
        return None
