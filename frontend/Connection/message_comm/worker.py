"""Network operations and retries; widgets are only updated by Tkinter."""
import base64
import uuid
from queue import Empty, Queue
from threading import Event, Thread

from nacl.public import Box, PublicKey
from frontend.Connection.login_and_register.key_generator import GenerateKey
from pymongo.errors import PyMongoError

from frontend.Connection.message_comm.recieve_message import ReceiveMessage
from frontend.Connection.message_comm.send_message import SendMessage


class MessageWorker:
    def __init__(self, login):
        self.login = login
        self.events = Queue()
        self.commands = Queue()
        self.stopped = Event()
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def send(self, recipient, message):
        message_id = str(uuid.uuid4())
        self.commands.put(("send", message_id, recipient, message))
        return message_id

    def read(self, ids):
        self.commands.put(("read", ids))

    def close(self):
        self.stopped.set()

    def _sync(self, client, since, known):
        if self.login.private_key is None:
            return since
        docs = client.history_updates(since)
        delivered = []
        for doc in docs:
            message_id = str(doc["_id"])
            outgoing = doc["sender"] == self.login.username
            peer = doc["recipient"] if outgoing else doc["sender"]
            key = client.public_key_for(peer)
            if key["type"] == "error":
                continue
            try:
                plaintext = Box(self.login.private_key, PublicKey(base64.b64decode(key["public_key"]))).decrypt(
                    base64.b64decode(doc["ciphertext"])).decode("utf-8")
            except Exception:
                self.events.put(("notice", "Не вдалося розшифрувати повідомлення. Перевірте приватний ключ."))
                continue
            row = dict(id=message_id, peer=peer, text=plaintext, outgoing=outgoing,
                       time=doc["time"], status="прочитано" if doc.get("read") else
                       "доставлено" if doc.get("delivered") else "відправлено")
            if known.get(message_id) != row:
                known[message_id] = row
                self.events.put(("message", row))
            if not outgoing and not doc.get("delivered"):
                delivered.append(message_id)
            updated = doc.get("updated_at")
            if updated is not None and (since is None or updated > since):
                since = updated
        if delivered:
            client.acknowledge(delivered)
        return since

    def _run(self):
        client = self.login.server_client
        sender = SendMessage(client)
        receiver = ReceiveMessage(client)
        direct = hasattr(client, "history_updates")
        since, known, pending = None, {}, None
        delay = 1
        try:
            while not self.stopped.is_set():
                try:
                    if pending is None:
                        try:
                            pending = self.commands.get_nowait()
                        except Empty:
                            pass
                    if pending:
                        if pending[0] == "export":
                            _, destination, password = pending
                            try:
                                GenerateKey.export_key(self.login.private_key, self.login.username, password, destination)
                                self.events.put(("notice", "Зашифрований ключ експортовано."))
                            except (ValueError, OSError) as exc:
                                self.events.put(("notice", str(exc)))
                        elif pending[0] == "import":
                            _, source, password, account_password = pending
                            if direct and not client.verify_password(account_password):
                                self.events.put(("notice", "Неправильний пароль входу. Ключ не збережено."))
                                pending = None
                                continue
                            key = client.public_key_for(self.login.username)
                            try:
                                self.login.private_key = GenerateKey.import_key(source, password, self.login.username, key["public_key"], account_password)
                                since, known = None, {}
                                self.events.put(("notice", "Ключ імпортовано. Історію відновлено."))
                            except (ValueError, OSError) as exc:
                                self.events.put(("notice", str(exc)))
                        elif pending[0] == "read":
                            if direct:
                                client.acknowledge(pending[1], read=True)
                        else:
                            _, message_id, recipient, message = pending
                            result = sender.message_to_db(self.login, recipient, message, message_id)
                            self.events.put(("sent", message_id, recipient, message, result))
                        pending = None
                    if direct:
                        since = self._sync(client, since, known)
                        self.stopped.wait(0.5)
                    elif self.login.private_key is not None:
                        result = receiver.next_message(self.login.private_key, timeout=0.1)
                        if result is not None:
                            self.events.put(("received", result))
                    else:
                        self.stopped.wait(0.1)
                    if delay != 1:
                        self.events.put(("notice", "З’єднання відновлено."))
                    delay = 1
                except (PyMongoError, ConnectionError, OSError):
                    self.events.put(("notice", f"Немає з’єднання. Повторна спроба через {delay} с…"))
                    if self.stopped.wait(delay):
                        break
                    delay = min(delay * 2, 15)
                    # PyMongo reconnects its pool automatically. Keep the current
                    # command and its stable ID if an insert's outcome is unknown.
                    if not direct:
                        self.events.put(("error", "Увійдіть повторно для відновлення WebSocket-сеансу."))
                        break
                except Exception:
                    self.events.put(("error", "Не вдалося виконати операцію."))
                    pending = None
        finally:
            client.close()
