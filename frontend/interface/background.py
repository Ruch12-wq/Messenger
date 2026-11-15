"""Run slow work outside Tkinter; deliver results on its event loop."""
from queue import Empty, Queue
from threading import Thread


def run_background(widget, task, finished):
    results = Queue()

    def run():
        try:
            results.put((task(), None))
        except Exception as exc:
            results.put((None, exc))

    def poll():
        try:
            result, error = results.get_nowait()
        except Empty:
            widget.after(50, poll)
        else:
            finished(result, error)

    Thread(target=run, daemon=True).start()
    widget.after(50, poll)
