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
        