import sys
from pathlib import Path
from tkinter import Label, Tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from frontend.Connection.login_and_register.login import UserLogin
from frontend.interface.RegisterInterface import RegisterInterface
from frontend.Connection.server_client import MessengerServerClient
from frontend.interface.background import run_background
from frontend.interface.colors import Colors

class LoginInterface:
    def __init__(self):
        self.root = Tk()
        self.root.title("Log in")
        self.root.geometry("480x520")
        self.root.resizable(False, False)
        

        form = ttk.Frame(self.root, padding=32)
        form.pack(expand=True, fill="both")

        Label(
            form,
            text="Log in",
            font=("Arial", 20, "bold"),
            background=Colors.Light["BACKGROUND"],
            foreground=Colors.Light["TEXT"],
        ).pack(pady=(8, 24))
        ttk.Label(form, text="Connection (mongodb uses MONGO_URI from .env)").pack(anchor="w")
        self.server_entry = ttk.Entry(form)
        self.server_entry.insert(0, MessengerServerClient().url)
        self.server_entry.pack(fill="x", pady=(4, 14))

        ttk.Label(form, text="Username").pack(anchor="w")
        self.username_entry = ttk.Entry(form, width=38)
        self.username_entry.pack(fill="x", pady=(4, 14))

        ttk.Label(form, text="Password").pack(anchor="w")
        self.password_entry = ttk.Entry(form, width=38, show="*")
        self.password_entry.pack(fill="x", pady=(4, 18))

        actions = ttk.Frame(form)
        actions.pack(fill="x")
        actions.columnconfigure(0, weight=1, uniform="login-actions")
        actions.columnconfigure(1, weight=1, uniform="login-actions")

        self.login_button = ttk.Button(actions, text="Log in", command=self.log_in)
        self.login_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.register_button = ttk.Button(
            actions,
            text="Register",
            command=self.open_register_window,
        )
        self.register_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.busy = False
        self.status = ttk.Label(form, text="", wraplength=410)
        self.status.pack(pady=(12, 0))
        self.login = None
        self.register_window = None

    def open_register_window(self):
        if self.busy:
            return
        if self.register_window is not None and self.register_window.window.winfo_exists():
            self.register_window.window.focus_set()
            return
        self.register_window = RegisterInterface(self.root, self._registration_finished, self.server_entry.get().strip())

    def _registration_finished(self, message):
        self.status.configure(text=message)
        self.register_window = None

    def log_in(self):
        if self.busy:
            return
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.status.configure(text="Enter your username and password.")
            return
        self.busy = True
        self.login_button.configure(state="disabled")
        self.status.configure(text="Connecting…")
        # A fresh connection also allows retrying after the server was restarted.
        if self.login is not None:
            self.login.server_client.close()
        self.login = UserLogin(MessengerServerClient(self.server_entry.get().strip()))
        run_background(self.root, lambda: self.login.login_user(username, password), self._login_finished)

    def _login_finished(self, usercheck, error):
        self.busy = False
        self.login_button.configure(state="normal")
        if error is not None:
            self.login.server_client.close()
            self.status.configure(text=str(error))
            return

        if usercheck[1]:
            self.status.configure(text=f"Successfully logged in as '{self.login.username}'")
            from frontend.interface.intterface import MessengerInterface

            MessengerInterface(self.root, self.login)
        else:
            self.status.configure(text=usercheck[0])



if __name__ == "__main__":
    app = LoginInterface()
    app.root.mainloop()
