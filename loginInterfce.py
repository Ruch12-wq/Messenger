from tkinter import Tk
from tkinter import ttk

root = Tk()
root.title("Registeration")
root.geometry("900x780")

def log_in():
    window = Tk()
    window.title("Log in")
    window.geometry("900x780")
    root.destroy()
    window.mainloop()

btn = ttk.Button(text = "Log in", command = log_in)
btn.pack()







root.mainloop()