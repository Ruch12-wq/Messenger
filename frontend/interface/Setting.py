from tkinter import END, Text, Toplevel
from tkinter import ttk, filedialog, simpledialog

class SettingInterface:
    def __init__(self,login_root, login):
        self.login_root = login_root
        self.login = login
        self.window = Toplevel(login_root)
        self.window.title(f"Setting — {login.username}")
        self.window.geometry("500x700")
        self.window.minsize(500, 700)

    outer = ttk.Frame(padding=10)
    outer.pack(expand=True, fill="both")
    header = ttk.Frame(outer)
    header.pack(fill="x")

    

    def close(self):
        self.window.destroy()