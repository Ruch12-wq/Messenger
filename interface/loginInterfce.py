from tkinter import Tk, Text
from tkinter import ttk
from connection.login_and_register.login import UserLogin
from pathlib import Path



class LoginInterface:
    def __init__(self):
        self.root = Tk()
        self.root.title("Registeration")
        self.root.geometry("900x780")
        self.login = UserLogin()


    def log_in(self):
        window = Tk()
        window.title("Log in")
        window.geometry("900x780")
        self.root.destroy()
        window.mainloop()

        center = ttk.Frame(self.root)
        center.pack(expand=True, fill="both")

        #name
        editorname = ttk.Entry(center, width=40, height=1.5, font = "Arial 15")
        editorname.place(relx=0.5, rely=0.35, anchor="center")
        #password
        editorpassword = ttk.Entry(center, width=40, height=3)
        editorpassword.place(relx=0.5, rely=0.5, anchor="center")


        btn = ttk.Button(self, text="Log in", command=log_in)
        btn.pack(side="bottom", anchor="e", pady=40, padx=250)


        self.root.mainloop()
