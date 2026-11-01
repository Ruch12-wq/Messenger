"""Desktop frontend entry point (use the root launcher to install dependencies)."""
from frontend.interface.loginInterfce import LoginInterface


def main():
    app = LoginInterface()
    app.root.mainloop()


if __name__ == "__main__":
    main()
