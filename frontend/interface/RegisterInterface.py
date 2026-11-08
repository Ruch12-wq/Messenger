"""Registration dialog for the desktop client."""
from tkinter import Toplevel
from tkinter import ttk

from frontend.Connection.login_and_register.register import UserLoginRegister


class RegisterInterface:
    def __init__(self, parent, on_finished=None):
        self.on_finished = on_finished
        self.window = Toplevel(parent)
        self.window.title("Register")
        self.window.geometry("420x360")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        form = ttk.Frame(self.window, padding=32)
        form.pack(expand=True, fill="both")

        ttk.Label(form, text="Create an account", font=("Arial", 20, "bold")).pack(
            pady=(0, 20)
        )
        ttk.Label(form, text="Username").pack(anchor="w")
        self.username_entry = ttk.Entry(form, width=38)
        self.username_entry.pack(fill="x", pady=(4, 12))

        ttk.Label(form, text="Password (at least 16 characters)").pack(anchor="w")
        self.password_entry = ttk.Entry(form, width=38, show="*")
        self.password_entry.pack(fill="x", pady=(4, 12))

        ttk.Label(form, text="Confirm password").pack(anchor="w")
        self.confirm_password_entry = ttk.Entry(form, width=38, show="*")
        self.confirm_password_entry.pack(fill="x", pady=(4, 18))

        self.register_button = ttk.Button(form, text="Register", command=self.register)
        self.register_button.pack(anchor="e")
        self.status = ttk.Label(form, text="", wraplength=340)
        self.status.pack(pady=(12, 0))
        self.registration = None
        self.username_entry.focus_set()

    def close(self):
        if self.registration is not None:
            self.registration.server_client.close()
        self.window.destroy()
        if self.on_finished is not None:
            self.on_finished("")

    def register(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        confirmation = self.confirm_password_entry.get()
        if not username or not password:
            self.status.configure(text="Enter a username and password.")
            return
        if len(password) < 16:
            self.status.configure(text="The password must be at least 16 characters long.")
            return
        if password != confirmation:
            self.status.configure(text="The passwords do not match.")
            return

        try:
            if self.registration is None:
                self.registration = UserLoginRegister()
            result = self.registration.register_user(username, password)
        except Exception:
            self.status.configure(text="Cannot connect to the registration service.")
            return

        if result[1]:
            self.registration.server_client.close()
            self.registration = None
            self.window.destroy()
            if self.on_finished is not None:
                self.on_finished(result[0] + " You can now log in.")
        else:
            self.status.configure(text=result[0])
