import time
from threading import _BoundedSemaphore as BoundedSemaphore, Timer


class RatedSemaphore(BoundedSemaphore):
    """Limit to 1 request per `period / value` seconds (over long run).

    From http://stackoverflow.com/a/33224087/62269.
    """
    def __init__(self, value=1, period=1):
        BoundedSemaphore.__init__(self, value)
        t = Timer(period, self._add_token_loop,
                  kwargs=dict(time_delta=float(period) / value))
        t.daemon = True
        t.start()

    def _add_token_loop(self, time_delta):
        """Add token every time_delta seconds."""
        while True:
            try:
                BoundedSemaphore.release(self)
            except ValueError: # ignore if already max possible value
                pass
            time.sleep(time_delta) # ignore EINTR

    def release(self):
        pass # do nothing (only time-based release() is allowed)
