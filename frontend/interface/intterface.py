"""The main messenger window shown after a successful login."""
from queue import Empty
from tkinter import END, Text, Toplevel
from tkinter import ttk

from frontend.Connection.message_comm.worker import MessageWorker


class MessengerInterface:
    def __init__(self, login_root, login):
        self.login_root = login_root
        self.login = login
        self.window = Toplevel(login_root)
        self.window.title(f"Messenger — {login.username}")
        self.window.geometry("680x500")
        self.window.minsize(500, 360)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.login_root.withdraw()

        outer = ttk.Frame(self.window, padding=16)
        outer.pack(expand=True, fill="both")
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text=f"Logged in as {login.username}", font=("Arial", 12, "bold")).pack(
            side="left"
        )
        ttk.Label(header, text="To:").pack(side="left", padx=(24, 4))
        self.recipient_entry = ttk.Entry(header, width=24)
        self.recipient_entry.pack(side="left")

        self.history = Text(outer, height=18, state="disabled", wrap="word")
        self.history.pack(expand=True, fill="both", pady=12)

        composer = ttk.Frame(outer)
        composer.pack(fill="x")
        self.message_entry = ttk.Entry(composer)
        self.message_entry.pack(side="left", expand=True, fill="x")
        self.message_entry.bind("<Return>", self.send)
        self.send_button = ttk.Button(composer, text="Send", command=self.send)
        self.send_button.pack(side="left", padx=(8, 0))
        self.status = ttk.Label(outer, text="")
        self.status.pack(anchor="w", pady=(8, 0))

        self.sending = False
        self.worker = MessageWorker(login)
        if login.private_key is None:
            self.status.configure(
                text="Private key is not available on this device; incoming messages cannot be decrypted."
            )
        self.message_entry.focus_set()
        self.poll_messages()

    def append(self, text):
        self.history.configure(state="normal")
        self.history.insert(END, text + "\n")
        self.history.see(END)
        self.history.configure(state="disabled")

    def send(self, _event=None):
        recipient = self.recipient_entry.get().strip()
        message = self.message_entry.get().strip()
        if not recipient or not message:
            self.status.configure(text="Enter a recipient and a message.")
            return "break"
        if self.login.private_key is None:
            self.status.configure(text="This device does not have your private key.")
            return "break"
        if self.sending:
            return "break"
        self.sending = True
        self.send_button.configure(state="disabled")
        self.status.configure(text="Sending…")
        self.worker.send(recipient, message)
        return "break"

    def poll_messages(self):
        # Only the main Tkinter thread touches widgets. Drain all available
        # events so a burst of messages doesn't wait one timer tick per item.
        while True:
            try:
                event = self.worker.events.get_nowait()
            except Empty:
                break
            if event[0] == "sent":
                _, recipient, message, result = event
                self.sending = False
                self.send_button.configure(state="normal")
                if result[1]:
                    self.append(f"You → {recipient}: {message}")
                    if self.message_entry.get().strip() == message:
                        self.message_entry.delete(0, END)
                self.status.configure(text=result[0])
            elif event[0] == "received":
                result = event[1]
                if result[-1]:
                    self.append(f"{result[0]}: {result[1]}")
                else:
                    self.status.configure(text=result[0])
            else:
                self.sending = False
                self.send_button.configure(state="disabled")
                self.status.configure(text=event[1])
        self.poll_id = self.window.after(50, self.poll_messages)

    def close(self):
        self.window.after_cancel(self.poll_id)
        self.worker.close()
        self.window.destroy()
        self.login_root.deiconify()
