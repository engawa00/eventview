import tkinter as tk
from tkinter import ttk
import time
from event_viewer import CalendarDialog

def run_benchmark():
    root = tk.Tk()
    entry = ttk.Entry(root)
    entry.insert(0, "2023-10-01")

    # Override grab_set to prevent it from blocking/erroring in headless
    old_grab_set = tk.Toplevel.grab_set
    tk.Toplevel.grab_set = lambda self: None

    dialog = CalendarDialog(root, entry)

    # Force initial update to make sure it's rendered
    root.update()

    start = time.time()
    for _ in range(1000):
        dialog.add_months(1)
        dialog.update_idletasks() # Ensure UI work is processed
    end = time.time()

    print(f"Time taken for 1000 month switches: {end - start:.4f} seconds")
    dialog.destroy()
    root.destroy()

    tk.Toplevel.grab_set = old_grab_set

if __name__ == "__main__":
    run_benchmark()
