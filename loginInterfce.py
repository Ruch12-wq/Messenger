from tkinter import Tk, Text
from tkinter import ttk

root = Tk()
root.title("Registeration")
root.geometry("900x780")


center = ttk.Frame(root)
center.pack(expand=True, fill="both")

#name
editorname = Text(center, width=40, height=1.5, font = "Arial 15")
editorname.place(relx=0.5, rely=0.35, anchor="center")
#password
editorpassword = Text(center, width=40, height=3)
editorpassword.place(relx=0.5, rely=0.5, anchor="center")

CORRECT_PASSWORD = "123"


def current_password():
    return editorpassword.get("1.0", "end-1c").strip()


def update_button(event=None):
    if current_password() == CORRECT_PASSWORD:
        btn.state(["!disabled"])
    else:
        btn.state(["disabled"])


def log_in():
    if current_password() != CORRECT_PASSWORD:
        return
    window = Tk()
    window.title("Log in")
    window.geometry("900x780")
    root.destroy()
    window.mainloop()


btn = ttk.Button(root, text="Log in", command=log_in)
btn.pack(side="bottom", anchor="e", pady=40, padx=250)
btn.state(["disabled"])
editorpassword.bind("<KeyRelease>", update_button)


root.mainloop()
