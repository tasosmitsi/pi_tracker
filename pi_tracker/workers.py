import threading
import logging
import signal
import time

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib

from pi_tracker.failure_log import FailureLog

log = logging.getLogger(__name__)

def run_with_main_loop(*works, stop_timeout_s=15):
    """Run each work(stop_event) in a thread of its own while the GLib main loop runs; return the exit code.

    The workers share stop_event. SIGINT (Ctrl+C) and SIGTERM (systemctl stop) set
    it, and so does any worker that ends, so they all stop together; the loop ends
    when the last one has. A second signal, or workers still busy stop_timeout_s
    after the stop began, end it without waiting. The exit code is 1 when a worker
    failed, ended by itself or had to be abandoned, so systemd can restart the app;
    0 after a clean stop. Each thread is named after its work function.
    """
    if not works:
        raise ValueError("run_with_main_loop needs at least one worker")
    loop = GLib.MainLoop()
    stop_event = threading.Event()
    failed = []        # appended to by the worker threads or by give_up()
    timeouts = []
    signals = []       # the signals received so far
    running = len(works)

    def give_up(reason):
        log.error("%s, exiting without waiting any longer", reason)
        failed.append(reason)
        loop.quit()
        return False   # a one-off GLib timeout

    def begin_stop():
        """Ask every worker to stop, and give them stop_timeout_s."""
        if not stop_event.is_set():
            stop_event.set()
            timeouts.append(GLib.timeout_add(int(stop_timeout_s * 1000), give_up,
                                             "Still stopping after %s s" % stop_timeout_s))

    def on_signal(signum, frame):
        name = signal.Signals(signum).name
        if signals:
            give_up("%s again" % name)
            return
        signals.append(name)
        log.info("%s received, stopping", name)
        begin_stop()

    def on_worker_done():  # on the main loop, once per worker
        nonlocal running
        running -= 1
        if running == 0:
            loop.quit()
        else:
            begin_stop()   # one worker ending stops the others
        return False

    def worker(work):
        name = threading.current_thread().name
        try:
            work(stop_event)
        except BaseException:
            log.exception("Worker %s failed, exiting", name)
            failed.append(name)
        else:
            if not stop_event.is_set():
                log.error("Worker %s ended without being asked to, exiting", name)
                failed.append(name)
        finally:
            GLib.idle_add(on_worker_done)

    previous = {signum: signal.signal(signum, on_signal) for signum in (signal.SIGINT, signal.SIGTERM)}
    threads = [threading.Thread(target=worker, args=(work,), name=_thread_name(work, number), daemon=True)
               for number, work in enumerate(works, 1)]  # daemon: a stuck one can't block the exit
    try:
        for thread in threads:
            thread.start()
        loop.run()
        if not failed:
            for thread in threads:
                thread.join(1)
    finally:
        for source in timeouts:
            if GLib.MainContext.default().find_source_by_id(source):  # it's gone once it has fired
                GLib.source_remove(source)
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 1 if failed or any(thread.is_alive() for thread in threads) else 0


def _thread_name(work, number):
    name = getattr(work, '__name__', '')
    return name if name and not name.startswith('<') else 'worker-%d' % number  # a lambda is '<lambda>'


class StoppableRestartableGiThread:
    def __init__(self, target, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.thread = None
        self._failures = FailureLog("Thread %s" % target.__name__, log)


    def start(self, delay):
        if self.thread is None:
            self.thread = GLib.timeout_add_seconds(delay, self._run)
            
        else:
            log.warning("Thread %s is already running.", self.target.__name__)
        return self

    def stop(self):
        if self.thread is not None:
            GLib.source_remove(self.thread)
            self.thread = None
            log.info("Thread %s is now stopped.", self.target.__name__)
            
        else:
            log.warning("Thread %s is already stopped.", self.target.__name__)
        return self

    def is_running(self):
        return self.thread is not None

    def _run(self):
        # GLib drops a timer for good when its callback raises, so a single failed
        # read would stop it. Log the error and keep the timer running instead.
        try:
            keep_going = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self._failures.failed(e)
            return True

        self._failures.succeeded()
        if not keep_going:
            # GLib removes the timer itself when the callback returns a false value
            self.thread = None
        return keep_going
