import sys
from pathlib import Path
from tkinter import Tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from frontend.Connection.login_and_register.login import UserLogin
from frontend.interface.RegisterInterface import RegisterInterface

class LoginInterface:
    def __init__(self):
        self.root = Tk()
        self.root.title("Log in")
        self.root.geometry("420x380")
        self.root.resizable(False, False)

        form = ttk.Frame(self.root, padding=32)
        form.pack(expand=True, fill="both")

        ttk.Label(form, text="Log in", font=("Arial", 20, "bold")).pack(pady=(8, 24))
        ttk.Label(form, text="Username").pack(anchor="w")
        self.username_entry = ttk.Entry(form, width=38)
        self.username_entry.pack(fill="x", pady=(4, 14))

        ttk.Label(form, text="Password").pack(anchor="w")
        self.password_entry = ttk.Entry(form, width=38, show="*")
        self.password_entry.pack(fill="x", pady=(4, 18))

        ttk.Button(form, text="Log in", command=self.log_in).pack(anchor="e")
        self.status = ttk.Label(form, text="")
        self.status.pack(pady=(12, 0))
        self.login = None
        self.register_window = None
        ttk.Button(
            form,
            text="Register",
            command=self.open_register_window,
            padding=(0, 8),
        ).pack(
            anchor="w", pady=(8, 0)
        )

    def open_register_window(self):
        if self.register_window is not None and self.register_window.window.winfo_exists():
            self.register_window.window.focus_set()
            return
        self.register_window = RegisterInterface(self.root, self._registration_finished)

    def _registration_finished(self, message):
        self.status.configure(text=message)
        self.register_window = None

    def log_in(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.status.configure(text="Enter your username and password.")
            return
        try:
            if self.login is None:
                self.login = UserLogin()
            usercheck = self.login.login_user(username, password)
        except Exception:
            self.status.configure(
                text="Cannot connect to the login service. Check your database credentials."
            )
            return

        if usercheck[1]:
            self.status.configure(text=f"Successfully logged in as '{username}'")
            from frontend.interface.intterface import MessengerInterface

            MessengerInterface(self.root, self.login)
        else:
            self.status.configure(text=usercheck[0])



if __name__ == "__main__":
    app = LoginInterface()
    app.root.mainloop()
