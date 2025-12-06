
import time
import heapq
import threading
from py_model.libs.__utils import py_log

class FlowTimeoutManager:
    def __init__(self, table, default_ttl):
        self.table = table
        self.default_ttl = default_ttl
        self.heap = []           # list of (expire_at, hash)
        self.expire_at = {}      # hash -> expire_at
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def add_or_refresh(self, hash, ttl=None):
        if ttl is None:
            ttl = self.default_ttl
        now = time.time()
        exp = now + ttl
        with self.lock:
            self.expire_at[hash] = exp
            heapq.heappush(self.heap, (exp, hash))
            self.cv.notify()

    def remove(self, hash):
        with self.lock:
            self.table.delete(hash)
            self.expire_at.pop(hash, None)
            self.cv.notify()

    def _run(self):
        while True:
            with self.lock:
                while True:
                    if not self.heap:
                        # wait until something is added
                        self.cv.wait()
                        continue
                    exp, h = self.heap[0]
                    now = time.time()
                    if exp > now:
                        # sleep until next expiry or a wakeup
                        timeout = exp - now
                        self.cv.wait(timeout=timeout)
                        continue
                    # time reached; pop and see if it's still valid
                    heapq.heappop(self.heap)
                    current_exp = self.expire_at.get(h)
                    if current_exp is None or current_exp != exp:
                        # stale entry, skip
                        continue
                    # valid timeout; remove from map and delete from table
                    del self.expire_at[h]
                    break

            # perform delete outside the lock
            try:
                print(f"")
                py_log("info", f"[FlowTimeoutManager] expiring flow from table '{self.table.sai_table.name}'\n")
                self.table.delete(h)
            except Exception as e:
                py_log("warn", f"[FlowTimeoutManager] error deleting from table '{self.table.sai_table.name}'\n")
