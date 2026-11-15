"""Serialize socket operations off the Tkinter thread."""
from queue import Empty, Queue
from threading import Event, Thread

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
        self.commands.put((recipient, message))

    def close(self):
        self.stopped.set()

    def _run(self):
        sender = SendMessage(self.login.server_client)
        receiver = ReceiveMessage(self.login.server_client)
        try:
            while not self.stopped.is_set():
                try:
                    recipient, message = self.commands.get_nowait()
                except Empty:
                    pass
                else:
                    result = sender.message_to_db(self.login, recipient, message)
                    self.events.put(("sent", recipient, message, result))

                if self.login.private_key is None:
                    self.stopped.wait(0.1)
                    continue
                result = receiver.next_message(self.login.private_key, timeout=0.1)
                if result is not None:
                    self.events.put(("received", result))
        except Exception:
            self.events.put(("error", "Connection to the server was lost."))
        finally:
            self.login.server_client.close()
