import time
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import tkinter as tk
from unittest.mock import patch
import event_viewer

def test_gui_freeze():
    # Because we run in CI, we need a virtual display or mock tk?
    # Actually wait, we might get TclError if there's no display.
    try:
        root = tk.Tk()
    except tk.TclError:
        print("Max mainloop delay: N/A (No display)")
        return

    app = event_viewer.WakeEventViewerApp(root)

    def mock_get_wake_events(start, end):
        time.sleep(2)
        return [{"SleepTime": "2023-01-01", "WakeTime": "2023-01-02", "Reason": "Test"}]

    start_time = time.time()
    delays = []

    def monitor():
        delays.append(time.time())
        if time.time() - start_time < 3:
            root.after(100, monitor)
        else:
            root.destroy()

    root.after(100, monitor)

    with patch("event_viewer.get_wake_events", side_effect=mock_get_wake_events):
        root.after(500, app.fetch_data)
        root.mainloop()

    intervals = [delays[i] - delays[i-1] for i in range(1, len(delays))]
    max_delay = max(intervals) if intervals else 0
    print(f"Max mainloop delay: {max_delay:.2f} seconds")

if __name__ == "__main__":
    test_gui_freeze()
