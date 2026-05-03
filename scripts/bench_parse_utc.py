import timeit
import datetime
import os
from event_viewer import parse_utc_to_local, UTC_FORMATS


# Original function logic (re-implemented here for baseline)
def parse_utc_to_local_original(utc_str: str) -> str:
    if not utc_str:
        return ""

    parsed_str = utc_str
    if len(utc_str) >= 20 and utc_str[-1] == "Z" and utc_str[10] == "T":
        if "." in utc_str:
            base, frac = utc_str[:-1].split(".", 1)
            parsed_str = f"{base}.{frac[:6]}Z"

    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt_utc = datetime.datetime.strptime(parsed_str, fmt).replace(
                tzinfo=datetime.timezone.utc
            )
            dt_local = dt_utc.astimezone()
            return dt_local.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    return utc_str


test_str = "2023-10-27T12:00:00.123456Z"

if __name__ == "__main__":
    n = 100000
    t_original = timeit.timeit(lambda: parse_utc_to_local_original(test_str), number=n)
    t_optimized = timeit.timeit(lambda: parse_utc_to_local(test_str), number=n)

    print(f"Original: {t_original:.6f}s")
    print(f"Optimized: {t_optimized:.6f}s")
    print(f"Improvement: {(t_original - t_optimized) / t_original * 100:.2f}%")
