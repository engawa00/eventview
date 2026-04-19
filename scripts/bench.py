import timeit
import os
import functools

def original() -> str:
    return os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wevtutil.exe")

@functools.lru_cache(maxsize=1)
def cached() -> str:
    return os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wevtutil.exe")

if __name__ == "__main__":
    print("Baseline:", timeit.timeit(original, number=1000000))
    print("Cached:", timeit.timeit(cached, number=1000000))
