import timeit
import os
import functools

def original():
    return os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'wevtutil.exe')

@functools.lru_cache(maxsize=1)
def cached():
    return os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'wevtutil.exe')

print("Baseline:", timeit.timeit(original, number=1000000))
print("Cached:", timeit.timeit(cached, number=1000000))
