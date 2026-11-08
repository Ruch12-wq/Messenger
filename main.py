"""Install dependencies in an isolated environment and launch Messenger."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import venv

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".venv"
PYTHON = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def configure_console_encoding():
    """Allow Ukrainian status messages to work in older Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def prepare(component):
    if not PYTHON.exists():
        print("Створення віртуального середовища…", flush=True)
        venv.EnvBuilder(with_pip=True).create(ENV)
    requirements = ROOT / "requirements.txt" if component == "all" else ROOT / component / "requirements.txt"
    print("Перевірка та встановлення залежностей…", flush=True)
    subprocess.run(
        [str(PYTHON), "-m", "pip", "install", "-r", str(requirements)],
        cwd=ROOT, check=True,
    )


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def wait_for_backend(process):
    # Read the same .env and defaults as the backend, using its environment.
    config = subprocess.check_output(
        [str(PYTHON), "-c", "from dotenv import load_dotenv; import os, json; "
         "load_dotenv('.env'); print(json.dumps([os.getenv('HOST', 'localhost'), "
         "int(os.getenv('PORT', '8765'))]))"], cwd=ROOT, text=True,
    )
    import json
    host, port = json.loads(config)
    if host in ("0.0.0.0", "::"):
        host = "localhost"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Backend завершився до запуску інтерфейсу. Перевірте повідомлення сервера.")
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Backend не запустився протягом 20 секунд.")


def main():
    configure_console_encoding()
    parser = argparse.ArgumentParser(description="Messenger: автоматичне встановлення бібліотек і запуск")
    parser.add_argument("component", nargs="?", choices=("all", "frontend", "backend"), default="all")
    parser.add_argument("--install-only", action="store_true", help="лише встановити залежності")
    args = parser.parse_args()
    processes = []
    try:
        prepare(args.component)
        if args.install_only:
            return 0
        if args.component in ("all", "backend"):
            server = subprocess.Popen([str(PYTHON), "-m", "backend.server"], cwd=ROOT)
            processes.append(server)
            if args.component == "backend":
                return server.wait()
            wait_for_backend(server)
        client = subprocess.Popen([str(PYTHON), "-m", "frontend.main"], cwd=ROOT)
        processes.append(client)
        while client.poll() is None:
            if args.component == "all" and server.poll() is not None:
                raise RuntimeError("Backend несподівано завершив роботу.")
            time.sleep(0.2)
        return client.returncode
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Помилка запуску: {exc}", file=sys.stderr)
        return 1
    finally:
        for process in reversed(processes):
            stop(process)


if __name__ == "__main__":
    sys.exit(main())
