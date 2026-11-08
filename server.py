"""Run the Messenger backend from the repository root.

This compatibility entry point supports ``python server.py`` as well as the
documented ``python -m backend.server`` command.
"""
import asyncio

from backend.server import main


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
