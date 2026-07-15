import time
from contextlib import contextmanager


class Timer:
    """Simple timer for measuring execution time."""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def start(self):
        """Start the timer."""
        self.start_time = time.time()

    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        self.end_time = time.time()
        if self.start_time is None:
            return 0.0
        return self.end_time - self.start_time

    def elapsed(self) -> float:
        """Get elapsed time without stopping."""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time


@contextmanager
def timer_context():
    """Context manager for timing code blocks."""
    timer = Timer()
    timer.start()
    try:
        yield timer
    finally:
        elapsed = timer.stop()
        print(f"Elapsed time: {elapsed:.3f}s")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
