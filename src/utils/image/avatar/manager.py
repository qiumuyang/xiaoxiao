import queue
import threading

from .fetch import Fetcher


class Manager:
    """Manages avatar fetching via a background queue and thread."""

    _queue: queue.Queue = queue.Queue()
    _stop_event = threading.Event()
    _worker_thread: threading.Thread | None = None

    @classmethod
    def start_worker(cls):
        """Starts the background worker thread."""
        if cls._worker_thread is None:
            cls._stop_event.clear()
            cls._worker_thread = threading.Thread(target=cls._worker_loop,
                                                  daemon=True)
            cls._worker_thread.start()

    @classmethod
    def stop_worker(cls):
        """Stops the background worker thread."""
        cls._stop_event.set()
        if cls._worker_thread:
            cls._worker_thread.join()
            cls._worker_thread = None

    @classmethod
    def enqueue(cls, *, id: int, is_group: bool):
        """Adds a fetch request to the queue."""
        cls._queue.put((id, is_group))

    @classmethod
    def _worker_loop(cls):
        """Processes fetch requests from the queue in the background."""
        while not cls._stop_event.is_set():
            try:
                id, is_group = cls._queue.get(timeout=1)
                Fetcher.fetch_avatar(id=id, is_group=is_group)
            except queue.Empty:
                continue
