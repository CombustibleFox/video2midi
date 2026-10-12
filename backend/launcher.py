"""Entry point for the packaged app: starts the server and opens the browser."""
import multiprocessing
import socket
import threading
import time
import webbrowser

import uvicorn

from app.main import app


def free_port(preferred: int = 8000) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("no free port")


def main() -> None:
    multiprocessing.freeze_support()  # the frame-analysis workers re-launch this executable
    port = free_port()
    url = f"http://127.0.0.1:{port}/"
    threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True).start()
    print(f"video2midi running at {url}  (close this window to quit)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
