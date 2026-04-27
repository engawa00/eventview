import pytest
import tkinter as tk
import os

def is_headless():
    return os.environ.get('GITHUB_ACTIONS') == 'true' or os.environ.get('DISPLAY') is None

def test_headless():
    if not is_headless():
        root = tk.Tk()
        print("Tk created")
    else:
        print("Headless, skipping Tk")

test_headless()
