# Agent Context and Guidelines

This file contains rules and guidelines for AI agents working on this repository.

## Project Overview
- This project is a Windows Wake Event Viewer tool that allows users to easily check the history and reasons for their PC waking up from sleep.
- It supports both a GUI mode (built with Tkinter) and a CLI mode, automatically switching based on provided arguments.
- The target OS requirement for this project is Windows 11.

## Architecture & Coding Practices
- **Mandatory Type Hinting:** All functions and methods must have Python type hints for arguments and return values.
- **Formatting Rules:** Comply with PEP 8 and use standards from `black` or `flake8` when modifying code.
- **README Sync:** Always update the relevant sections of `README.md` when adding user-facing features or changing command-line arguments.
- The repository includes a GUI event viewer in `event_viewer.py` built with Python's tkinter library.
- The project retrieves Windows event data by executing `wevtutil` from its absolute system path (e.g., within `System32`) and parsing its XML output. When parsing XML output from `wevtutil`, ensure to handle XML namespaces properly (e.g., `xmlns="http://schemas.microsoft.com/win/2004/08/events/event"`). When executing `wevtutil`, if an access denied error (Access Denied / Exception) occurs, implement error handling to output a clear, user-friendly message (in both GUI and CLI) prompting the user to run the application with Administrator privileges.
- Windows wake reason types ('0', '1', '8') in `event_viewer.py` are mapped to human-readable descriptions using a module-level dictionary named `WAKE_TYPE_REASONS`.
- Functions in `event_viewer.py` (such as `get_wake_events`) use standard Python exceptions (like `RuntimeError` and `ValueError`) for error handling, which are then caught and displayed by the CLI and GUI call sites using `try...except` blocks.
- To prevent path hijacking, avoid using `shutil.which` or relying on the `PATH` environment variable for locating system utilities. Always prioritize hardcoded absolute paths, typically constructed using `os.environ.get('SystemRoot', 'C:\\Windows')` to point directly to `System32` for Windows tools.
- UX and UI enhancements should be kept concise (under 50 lines of code) and should utilize existing formatting/styling libraries in the project without introducing heavy new dependencies (like `rich` or `textual`) unless they are already present.
- When clearing or updating Tkinter Treeview items, prefer batched operations (e.g., `self.tree.delete(*self.tree.get_children())`) over individual item iteration to minimize overhead from Tcl/Tk interpreter transitions.

## Environment & Setup
- To set up the development environment and install dependencies such as testing frameworks, run `pip install -r requirements-dev.txt`.
- The project uses GitHub Actions for CI/CD, with workflows defined in the `.github/workflows/` directory (e.g., running Python unit tests on `windows-latest` runners).

## Testing
- The project uses `pytest` for testing.
- To run the project's tests, use the command `pytest test_event_viewer.py`.
- When testing `event_viewer.py`, especially to prevent `TclError` in headless CI environments, aggressively mock GUI components when testing business logic, or use environment variables before test execution to determine if mocking is necessary.

## Execution & Planning
- Expected execution commands: `python event_viewer.py --cli` for CLI mode, and `python event_viewer.py` for GUI mode. Use these to plan tests accurately.
- Execution plans must explicitly include a step to run the test suite (e.g., using `pytest`) to verify tests pass and no regressions are introduced before proceeding to the pre-commit and submission stages.
- Execution plans must include a step with the exact phrasing: 'Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.'
