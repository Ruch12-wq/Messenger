"""The main messenger window shown after a successful login."""
from queue import Empty
from tkinter import END, Text, Toplevel
from tkinter import ttk, filedialog, simpledialog
import time

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
        outer.pack(expand=True, fill="both", padx=(200, 0))
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text=f"Logged in as {login.username}", font=("Arial", 12, "bold")).pack(
            side="left"
        )
        ttk.Label(header, text="To:").pack(side="left", padx=(24, 4))
        self.recipient_entry = ttk.Entry(header, width=24)
        self.recipient_entry.pack(side="left")

        tools = ttk.Frame(outer)
        tools.pack(fill="x", pady=(8, 0))
        ttk.Button(tools, text="Експорт ключа", command=self.export_key).pack(side="left")
        ttk.Button(tools, text="Імпорт ключа", command=self.import_key).pack(side="left", padx=8)
        self.rows = {}
        self.read_requested = set()

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


        actions_s = ttk.Frame(outer, width=10)
        actions_s.pack(fill="x")
        self.setting_button = ttk.Button(actions_s, text="Settings", command=self.settings)
        self.setting_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))


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
        message_id = self.worker.send(recipient, message)
        self.rows[message_id] = dict(id=message_id, peer=recipient, text=message,
                                     outgoing=True, time=time.time(), status="відправляється")
        self.render_history()
        return "break"

    def poll_messages(self):
        # Only the main Tkinter thread touches widgets. Drain all available
        # events so a burst of messages doesn't wait one timer tick per item.
        dirty = False
        while True:
            try:
                event = self.worker.events.get_nowait()
            except Empty:
                break
            if event[0] == "sent":
                _, message_id, recipient, message, result = event
                self.sending = False
                self.send_button.configure(state="normal")
                if result[1]:
                    self.rows[message_id]["status"] = "відправлено"
                    dirty = True
                    if self.message_entry.get().strip() == message:
                        self.message_entry.delete(0, END)
                if not result[1]:
                    self.rows[message_id]["status"] = "помилка відправлення"
                    dirty = True
                self.status.configure(text=result[0])
            elif event[0] == "message":
                self.rows[event[1]["id"]] = event[1]
                dirty = True
            elif event[0] == "notice":
                self.status.configure(text=event[1])
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
        if dirty:
            self.render_history()
        if self.window.focus_displayof() is not None and self.window.state() == "normal":
            unread = [row["id"] for row in self.rows.values()
                      if not row["outgoing"] and row["status"] != "прочитано"
                      and row["id"] not in self.read_requested]
            if unread:
                self.read_requested.update(unread)
                self.worker.read(unread)
        self.poll_id = self.window.after(50, self.poll_messages)

    def render_history(self):
        position = self.history.yview()
        self.history.configure(state="normal")
        self.history.delete("1.0", END)
        for row in sorted(self.rows.values(), key=lambda row: (row["time"], row["id"])):
            who = f"Ви → {row['peer']}" if row["outgoing"] else row["peer"]
            stamp = time.strftime("%d.%m %H:%M", time.localtime(row["time"]))
            status = f" [{row['status']}]" if row["outgoing"] else ""
            self.history.insert(END, f"{stamp} {who}: {row['text']}{status}\n")
        self.history.configure(state="disabled")
        if position[1] >= 0.99:
            self.history.see(END)
        else:
            self.history.yview_moveto(position[0])

    def export_key(self):
        if self.login.private_key is None:
            self.status.configure(text="Спочатку імпортуйте приватний ключ.")
            return
        destination = filedialog.asksaveasfilename(parent=self.window, defaultextension=".mkey", filetypes=[("Encrypted key", "*.mkey")])
        if not destination:
            return
        password = simpledialog.askstring("Експорт ключа", "Окремий пароль перенесення (мінімум 16 символів):", show="*", parent=self.window)
        if not password:
            return
        confirmation = simpledialog.askstring("Експорт ключа", "Повторіть пароль перенесення:", show="*", parent=self.window)
        if password != confirmation or len(password) < 16:
            self.status.configure(text="Паролі мають збігатися та містити щонайменше 16 символів.")
            return
        self.worker.commands.put(("export", destination, password))

    def import_key(self):
        source = filedialog.askopenfilename(parent=self.window, filetypes=[("Encrypted key", "*.mkey")])
        if not source:
            return
        password = simpledialog.askstring("Імпорт ключа", "Пароль перенесення:", show="*", parent=self.window)
        if not password:
            return
        account_password = simpledialog.askstring("Імпорт ключа", "Ваш поточний пароль входу (для збереження ключа на цьому пристрої):", show="*", parent=self.window)
        if account_password:
            self.worker.commands.put(("import", source, password, account_password))

    def settings(self):
        from frontend.interface.Setting import SettingInterface
        self.setting_window = SettingInterface(self.window, self.login)


    def close(self):
        self.window.after_cancel(self.poll_id)
        self.worker.close()
        self.window.destroy()
        self.login_root.deiconify()
