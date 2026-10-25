"""
Encrypted messenger - SERVER

The server never sees plaintext messages or private keys. It only stores:
  * usernames, a hash of each user's login secret, and each user's PUBLIC key
  * encrypted messages (ciphertext) waiting to be delivered

Storage:
  * default: a local JSON file (server_data.json) - no database needed
  * if the MONGO_URI environment variable is set: MongoDB Atlas (or any MongoDB)

Run:  python server.py
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time

import websockets
from dotenv import load_dotenv
from websockets.exceptions import ConnectionClosed

load_dotenv()

HOST = os.environ.get("HOST", "localhost")      # "localhost" = only this computer
PORT = int(os.environ.get("PORT", "8765"))
# These names match the rest of the project. The older MONGODB_* names are
# accepted as a migration path for existing standalone server deployments.
MONGO_URI = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
MONGO_DB = os.environ.get("MONGO_DB") or os.environ.get("MONGODB_DB", "Messenger")
MONGO_COLLECTION_USERS = os.environ.get("MONGO_COLLECTION_USERS", "users_login")
MONGO_COLLECTION_MESSAGES = os.environ.get("MONGO_COLLECTION_MESSAGES", "messages")
DATA_FILE = os.environ.get("DATA_FILE", "server_data.json")

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")
MAX_CIPHERTEXT_CHARS = 200_000

store = None        # set in main()
connected = {}      # username -> set of open connections (one user, several devices)


# --------------------------------------------------------------------------
# Storage back-ends
# --------------------------------------------------------------------------
class FileStore:
    """Keeps everything in one JSON file. Fine for local testing."""

    def __init__(self, path):
        self.path = path
        self.data = {"users": {}, "messages": []}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)

    async def init(self):
        pass

    async def create_user(self, user, salt, hashed, public_key):
        if user in self.data["users"]:
            return False
        self.data["users"][user] = {
            "user": user, "salt": salt, "hash": hashed, "public_key": public_key,
        }
        self._save()
        return True

    async def get_user(self, user):
        return self.data["users"].get(user)

    async def add_message(self, sender, to, ciphertext):
        message_id = secrets.token_hex(8)
        self.data["messages"].append({
            "id": message_id, "from": sender, "to": to, "ciphertext": ciphertext,
            "time": time.time(), "delivered": False,
        })
        self._save()
        return message_id

    async def undelivered(self, user):
        return [dict(m) for m in self.data["messages"]
                if m["to"] == user and not m["delivered"]]

    async def mark_delivered(self, ids):
        ids = set(ids)
        for m in self.data["messages"]:
            if m["id"] in ids:
                m["delivered"] = True
        self._save()


class MongoStore:
    """Stores data in the MongoDB collections configured for this project."""

    def __init__(self, uri, db_name, users_collection, messages_collection):
        from pymongo import AsyncMongoClient   # needs pymongo >= 4.13
        self.client = AsyncMongoClient(uri, serverSelectionTimeoutMS=8000)
        db = self.client[db_name]
        self.users = db[users_collection]
        self.messages = db[messages_collection]

    async def init(self):
        await self.client.admin.command("ping")          # fail early if unreachable
        await self.users.create_index("username", unique=True)
        await self.messages.create_index([("recipient", 1), ("delivered", 1)])

    async def create_user(self, user, salt, hashed, public_key):
        from pymongo.errors import DuplicateKeyError
        try:
            await self.users.insert_one({
                "username": user, "salt": salt, "hash": hashed,
                "public_key": public_key,
            })
            return True
        except DuplicateKeyError:
            return False

    async def get_user(self, user):
        return await self.users.find_one({"username": user})

    async def add_message(self, sender, to, ciphertext):
        result = await self.messages.insert_one({
            "sender": sender, "recipient": to, "ciphertext": ciphertext,
            "time": time.time(), "delivered": False,
        })
        return result.inserted_id

    async def undelivered(self, user):
        docs = await self.messages.find(
            {"recipient": user, "delivered": False}).sort("time", 1).to_list(None)
        return [{"id": d["_id"], "from": d["sender"],
                 "ciphertext": d["ciphertext"], "time": d["time"]} for d in docs]

    async def mark_delivered(self, ids):
        ids = list(ids)
        if ids:
            await self.messages.update_many(
                {"_id": {"$in": ids}}, {"$set": {"delivered": True}})


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def hash_secret(secret, salt):
    """Slow, salted hash (scrypt) so a stolen database can't be cheaply cracked."""
    return hashlib.scrypt(secret.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def valid_public_key(text):
    try:
        return len(base64.b64decode(text, validate=True)) == 32
    except Exception:
        return False


def valid_secret(text):
    return isinstance(text, str) and 16 <= len(text) <= 256


async def send_json(ws, obj):
    await ws.send(json.dumps(obj))


async def fail(ws, text):
    await send_json(ws, {"type": "error", "message": text})


def log(text):
    print(time.strftime("[%H:%M:%S] ") + text, flush=True)


async def deliver_backlog(ws, user):
    """Send messages that arrived while the user was offline."""
    sent_ids = []
    for m in await store.undelivered(user):
        try:
            await send_json(ws, {"type": "new_message", "id": str(m["id"]),
                                 "from": m["from"], "ciphertext": m["ciphertext"],
                                 "time": m["time"]})
        except ConnectionClosed:
            break
        sent_ids.append(m["id"])
    await store.mark_delivered(sent_ids)
    if sent_ids:
        log(f"delivered {len(sent_ids)} stored message(s) to {user}")


async def start_session(ws, session, user):
    session["user"] = user
    connected.setdefault(user, set()).add(ws)


# --------------------------------------------------------------------------
# Request handling
# --------------------------------------------------------------------------
async def process(ws, session, msg):
    kind = msg.get("type")
    user = session["user"]

    if kind == "register":
        if user:
            return await fail(ws, "You are already logged in.")
        name = str(msg.get("user", "")).strip().lower()
        secret, public_key = msg.get("login_secret"), msg.get("public_key")
        if not USERNAME_RE.match(name):
            return await fail(ws, "Username must be 3-20 characters: letters, digits, underscore.")
        if not valid_secret(secret) or not valid_public_key(public_key):
            return await fail(ws, "Invalid registration data.")
        salt = secrets.token_bytes(16)
        hashed = await asyncio.to_thread(hash_secret, secret, salt)
        if not await store.create_user(name, salt.hex(), hashed.hex(), public_key):
            return await fail(ws, "That username is already taken.")
        await start_session(ws, session, name)
        log(f"{name} registered")
        await send_json(ws, {"type": "ok", "action": "register", "user": name})

    elif kind == "login":
        if user:
            return await fail(ws, "You are already logged in.")
        name = str(msg.get("user", "")).strip().lower()
        secret = msg.get("login_secret")
        if not valid_secret(secret):
            return await fail(ws, "Wrong username or password.")
        record = await store.get_user(name)
        salt = bytes.fromhex(record["salt"]) if record and "salt" in record else bytes(16)
        hashed = await asyncio.to_thread(hash_secret, secret, salt)   # same work either way
        if not record or "hash" not in record or not hmac.compare_digest(hashed.hex(), record["hash"]):
            return await fail(ws, "Wrong username or password.")
        await start_session(ws, session, name)
        log(f"{name} logged in")
        await send_json(ws, {"type": "ok", "action": "login", "user": name})
        await deliver_backlog(ws, name)

    elif kind == "get_key":
        if not user:
            return await fail(ws, "Please log in first.")
        name = str(msg.get("user", "")).strip().lower()
        record = await store.get_user(name)
        if not record:
            return await fail(ws, "No such user.")
        await send_json(ws, {"type": "key", "user": name,
                             "public_key": record["public_key"]})

    elif kind == "send":
        if not user:
            return await fail(ws, "Please log in first.")
        to = str(msg.get("to", "")).strip().lower()
        ciphertext = msg.get("ciphertext")
        if not isinstance(ciphertext, str) or not ciphertext or len(ciphertext) > MAX_CIPHERTEXT_CHARS:
            return await fail(ws, "Invalid message.")
        if not await store.get_user(to):
            return await fail(ws, "No such user.")
        message_id = await store.add_message(user, to, ciphertext)   # save first
        payload = {"type": "new_message", "id": str(message_id), "from": user,
                   "ciphertext": ciphertext, "time": time.time()}
        delivered = False
        for peer in list(connected.get(to, ())):
            try:
                await send_json(peer, payload)
                delivered = True
            except ConnectionClosed:
                pass
        if delivered:
            await store.mark_delivered([message_id])
        log(f"{user} -> {to} ({'delivered live' if delivered else 'stored for later'}, encrypted)")
        await send_json(ws, {"type": "sent", "delivered": delivered})

    else:
        await fail(ws, "Unknown request.")


async def handler(ws):
    session = {"user": None}
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError
            except ValueError:
                await fail(ws, "Invalid message format.")
                continue
            try:
                await process(ws, session, msg)
            except ConnectionClosed:
                raise
            except Exception as e:
                log(f"error while handling a request: {e!r}")
                await fail(ws, "Server error.")
    except ConnectionClosed:
        pass
    finally:
        user = session["user"]
        if user and user in connected:
            connected[user].discard(ws)
            if not connected[user]:
                del connected[user]
            log(f"{user} disconnected")


async def main():
    global store
    if MONGO_URI:
        try:
            store = MongoStore(
                MONGO_URI, MONGO_DB, MONGO_COLLECTION_USERS,
                MONGO_COLLECTION_MESSAGES,
            )
            await store.init()
        except ImportError:
            sys.exit("MongoDB mode needs a recent pymongo:  pip install -U \"pymongo>=4.13\"")
        except Exception as e:
            sys.exit(
                f"Could not connect to MongoDB: {e}\n\n"
                "Check that:\n"
                "  1. the connection string was copied from Atlas > Connect > Drivers\n"
                "  2. the password in it is correct (special characters must be URL-encoded)\n"
                "  3. your CURRENT public IP address is in Atlas > Network Access\n"
                "To test without a database, unset MONGO_URI and the server uses a local file."
            )
        log(f"storage: MongoDB (database '{MONGO_DB}')")
    else:
        store = FileStore(DATA_FILE)
        log(f"storage: local file '{DATA_FILE}' (set MONGO_URI to use MongoDB)")

    async with websockets.serve(handler, HOST, PORT):
        log(f"server listening on ws://{HOST}:{PORT}   (Ctrl+C to stop)")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
