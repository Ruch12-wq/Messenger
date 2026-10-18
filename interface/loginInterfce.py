import sys
from pathlib import Path
from tkinter import Tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Connection.login_and_register.login import UserLogin

class LoginInterface:
    def __init__(self):
        self.root = Tk()
        self.root.title("Log in")
        self.root.geometry("420x320")
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

        ttk.Button(form, text="Log in", command=self.log_in).pack()
        self.status = ttk.Label(form, text="")
        self.status.pack(pady=(12, 0))
        self.login = None

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
        else:
            self.status.configure(text=usercheck[0])
        
    


if __name__ == "__main__":
    app = LoginInterface()
    app.root.mainloop()