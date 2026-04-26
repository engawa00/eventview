import pytest
from unittest.mock import patch, MagicMock
import datetime
import sys
import os

# Mock tkinter before importing event_viewer to avoid ModuleNotFoundError in environments without tkinter
try:
    import tkinter  # noqa: F401
except ImportError:
    sys.modules['tkinter'] = MagicMock()
    sys.modules['tkinter.ttk'] = MagicMock()
    sys.modules['tkinter.messagebox'] = MagicMock()

# Import the module to test
import event_viewer

def test_local_to_utc_str():
    # Test start of day formatting
    res_start = event_viewer.local_to_utc_str("2026-01-01", is_end_of_day=False)
    assert res_start.endswith("Z")
    assert "T" in res_start
    
    # Test end of day formatting
    res_end = event_viewer.local_to_utc_str("2026-01-01", is_end_of_day=True)
    assert res_end.endswith("Z")
    assert "T" in res_end
    
    # End should clearly be after start (alphabetically sorted time string comparison works here)
    assert res_start < res_end

def test_parse_utc_to_local_valid():
    # Provide a proper UTC string and observe conversion to local
    local_str = event_viewer.parse_utc_to_local("2026-01-01T12:00:00.123456Z")
    # Verify it can be parsed as local time format %Y-%m-%d %H:%M:%S
    try:
        dt = datetime.datetime.strptime(local_str, "%Y-%m-%d %H:%M:%S")
        assert True
    except ValueError:
        pytest.fail("Cannot parse the returned local time string")

def test_parse_utc_to_local_empty():
    assert event_viewer.parse_utc_to_local("") == ""
    assert event_viewer.parse_utc_to_local(None) == ""

def test_parse_utc_to_local_invalid():
    # Invalid string should just return as is when parsing fails
    assert event_viewer.parse_utc_to_local("invalid_date") == "invalid_date"

def test_parse_utc_to_local_value_error():
    # Invalid date with dot (fractional seconds) - Month 13
    invalid_with_dot = "2026-13-01T12:00:00.000Z"
    assert event_viewer.parse_utc_to_local(invalid_with_dot) == invalid_with_dot

    # Invalid date without dot - Day 32
    invalid_without_dot = "2026-01-32T12:00:00Z"
    assert event_viewer.parse_utc_to_local(invalid_without_dot) == invalid_without_dot

@patch('subprocess.run')
def test_get_wake_events_empty_output(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = b""
    mock_run.return_value = mock_result
    
    events = event_viewer.get_wake_events()
    assert events == []

@patch('subprocess.run')
def test_get_wake_events_success(mock_run):
    xml_data = """
    <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System>
        <EventID>1</EventID>
      </System>
      <EventData>
        <Data Name="SleepTime">2026-01-01T12:00:00.0000000Z</Data>
        <Data Name="WakeTime">2026-01-01T13:00:00.0000000Z</Data>
        <Data Name="WakeSourceType">8</Data>
        <Data Name="WakeSourceText">Network Adapter</Data>
      </EventData>
    </Event>
    <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System>
        <EventID>1</EventID>
      </System>
      <EventData>
        <Data Name="SleepTime">2026-01-02T12:00:00.000Z</Data>
        <Data Name="WakeTime">2026-01-02T13:00:00.000Z</Data>
        <Data Name="WakeSourceType">1</Data>
        <Data Name="WakeSourceText"></Data>
      </EventData>
    </Event>
    <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System>
        <EventID>1</EventID>
      </System>
      <EventData>
        <Data Name="SleepTime">2026-01-03T12:00:00.000Z</Data>
        <Data Name="WakeTime">2026-01-03T13:00:00.000Z</Data>
        <Data Name="WakeSourceType">0</Data>
        <Data Name="WakeSourceText"></Data>
      </EventData>
    </Event>
    <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System>
        <EventID>1</EventID>
      </System>
      <EventData>
        <Data Name="SleepTime">2026-01-04T12:00:00.000Z</Data>
        <Data Name="WakeTime">2026-01-04T13:00:00.000Z</Data>
        <Data Name="WakeSourceType">8</Data>
        <Data Name="WakeSourceText"></Data>
      </EventData>
    </Event>
    <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System>
        <EventID>1</EventID>
      </System>
      <EventData>
        <Data Name="SleepTime">2026-01-05T12:00:00.000Z</Data>
        <Data Name="WakeTime">2026-01-05T13:00:00.000Z</Data>
        <Data Name="WakeSourceType">5</Data>
        <Data Name="WakeSourceText"></Data>
      </EventData>
    </Event>
    <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
      <System>
        <EventID>1</EventID>
      </System>
      <EventData>
        <Data Name="SleepTime">2026-01-06T12:00:00.000Z</Data>
        <Data Name="WakeTime">2026-01-06T13:00:00.000Z</Data>
        <Data Name="WakeSourceType"></Data>
        <Data Name="WakeSourceText"></Data>
      </EventData>
    </Event>
    """
    mock_result = MagicMock()
    # Mocking stdout output with utf-8 payload
    mock_result.stdout = xml_data.encode('utf-8')
    mock_run.return_value = mock_result
    
    events = event_viewer.get_wake_events()
    assert len(events) == 6
    
    # Check first event
    assert events[0]["Reason"] == "Network Adapter"
    
    # Check second event (Empty WakeSourceText fallback to type 1 -> Power Button)
    assert events[1]["Reason"] == "電源ボタン (Power Button)"

    # Check third event (Empty WakeSourceText fallback to type 0 -> Unknown)
    assert events[2]["Reason"] == "不明 (Unknown)"

    # Check fourth event (Empty WakeSourceText fallback to type 8 -> Device / API)
    assert events[3]["Reason"] == "デバイス または API (Device / API)"

    # Check fifth event (Empty WakeSourceText fallback to type 5 -> Type 5)
    assert events[4]["Reason"] == "Type 5"

    # Check sixth event (Empty WakeSourceText and empty WakeSourceType fallback -> 不明)
    assert events[5]["Reason"] == "不明"

@patch('subprocess.run')
def test_get_wake_events_invalid_xml(mock_run):
    # Simulate invalid XML returned by wevtutil
    mock_result = MagicMock()
    mock_result.stdout = b"<Event><System><EventID>1</EventID></System>" # Missing closing tags
    mock_run.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        event_viewer.get_wake_events()
    assert "Failed to parse XML" in str(excinfo.value)

@patch('subprocess.run')
def test_get_wake_events_error(mock_run):
    # Simulate an OS error during subprocess run
    mock_run.side_effect = Exception("Command failed")
    
    with pytest.raises(Exception) as excinfo:
        event_viewer.get_wake_events()
    assert "Command failed" in str(excinfo.value)

@patch('subprocess.run')
def test_get_wake_events_query_with_dates(mock_run):
    # Mock return value to prevent error handling
    mock_result = MagicMock()
    mock_result.stdout = b"<Events></Events>"
    mock_run.return_value = mock_result

    start_date = "2026-01-01"
    end_date = "2026-01-02"

    # Mocking datetime for consistent timezone/UTC offset conversion could be needed,
    # but the test is asserting substring match so we can just check if dates are handled.
    event_viewer.get_wake_events(start_date=start_date, end_date=end_date)

    # Ensure subprocess.run was called
    assert mock_run.called

    # Extract the cmd argument
    args, kwargs = mock_run.call_args
    cmd = args[0]

    # Find the /q: query string argument
    query_arg = next((arg for arg in cmd if arg.startswith("/q:")), None)
    assert query_arg is not None

    # Check that time constraints are in the query
    assert "TimeCreated[" in query_arg
    assert "@SystemTime>=" in query_arg
    assert "@SystemTime<=" in query_arg

    # Convert dates via module function to check exact values
    expected_start = event_viewer.local_to_utc_str(start_date)
    expected_end = event_viewer.local_to_utc_str(end_date, is_end_of_day=True)

    assert f"@SystemTime>='{expected_start}'" in query_arg
    assert f"@SystemTime<='{expected_end}'" in query_arg
    assert " and " in query_arg[query_arg.find("TimeCreated["):]

def test_local_to_utc_str_invalid():
    with pytest.raises(ValueError) as excinfo:
        event_viewer.local_to_utc_str("invalid-date")
    assert "Invalid date format" in str(excinfo.value)

def test_get_wake_events_invalid_date():
    # Pass an invalid date string to get_wake_events
    with pytest.raises(ValueError) as excinfo:
        event_viewer.get_wake_events(start_date="not-a-date")
    assert "Invalid date format" in str(excinfo.value)

@patch('builtins.print')
@patch('event_viewer.get_wake_events')
def test_run_cli_empty(mock_get_events, mock_print):
    mock_get_events.return_value = []

    event_viewer.run_cli("2026-01-01", "2026-01-02")

    mock_get_events.assert_called_once_with(start_date="2026-01-01", end_date="2026-01-02")

    # Check that it printed the starting message
    mock_print.assert_any_call("スリープ復帰履歴を取得中... (開始: 2026-01-01, 終了: 2026-01-02)")
    # Check that it printed the not found message
    mock_print.assert_any_call("指定された期間の復帰イベントは見つかりませんでした。")

@patch('builtins.print')
@patch('event_viewer.get_wake_events')
def test_run_cli_error(mock_get_events, mock_print):
    mock_get_events.side_effect = Exception("Test error occurred")

    event_viewer.run_cli(None, None)

    mock_get_events.assert_called_once_with(start_date=None, end_date=None)

    # Check that it printed the error message
    mock_print.assert_any_call("エラー: Test error occurred")

@patch('builtins.print')
@patch('event_viewer.get_wake_events')
def test_run_cli_success(mock_get_events, mock_print):
    mock_get_events.return_value = [
        {"SleepTime": "2026-01-01 12:00:00", "WakeTime": "2026-01-01 13:00:00", "Reason": "Power Button"},
        {"SleepTime": "2026-01-02 12:00:00", "WakeTime": "2026-01-02 13:00:00", "Reason": "Network Adapter"}
    ]

    event_viewer.run_cli("2026-01-01", "2026-01-02")

    # Verify outputs
    mock_print.assert_any_call("スリープ復帰履歴を取得中... (開始: 2026-01-01, 終了: 2026-01-02)")
    mock_print.assert_any_call("-" * 80)
    mock_print.assert_any_call("[1] スリープ日時: 2026-01-01 12:00:00 | 復帰日時: 2026-01-01 13:00:00 | 理由: Power Button")
    mock_print.assert_any_call("[2] スリープ日時: 2026-01-02 12:00:00 | 復帰日時: 2026-01-02 13:00:00 | 理由: Network Adapter")

@patch('subprocess.run')
def test_execute_wevtutil_query_permission_error(mock_run):
    # Simulate a PermissionError when executing the command
    mock_run.side_effect = PermissionError("Access denied")

    with pytest.raises(RuntimeError) as excinfo:
        event_viewer._execute_wevtutil_query("*")

    assert "アクセスが拒否されました。アプリケーションを管理者権限で実行してください。" in str(excinfo.value)

@pytest.mark.parametrize("returncode, stdout, stderr", [
    (5, b"", b""),
    (0, b"Access is denied", b""),
    (0, b"\x83A\x83N\x83Z\x83X\x82\xaa\x8b\x91\x94\xdb\x82\xb3\x82\xea\x82\xdc\x82\xb5\x82\xbd", b""), # "アクセスが拒否されました" in CP932
    (0, b"", b"Access is denied"),
    (0, b"", b"\xe3\x82\xa2\xe3\x82\xaf\xe3\x82\xbb\xe3\x82\xb9\xe3\x81\x8c\xe6\x8b\x92\xe5\x90\xa6\xe3\x81\x95\xe3\x82\x8c\xe3\x81\xbe\xe3\x81\x97\xe3\x81\x9f"), # "アクセスが拒否されました" in UTF-8
])
@patch('subprocess.run')
def test_execute_wevtutil_query_access_denied_logic(mock_run, returncode, stdout, stderr):
    mock_result = MagicMock()
    mock_result.returncode = returncode
    mock_result.stdout = stdout
    mock_result.stderr = stderr
    mock_run.return_value = mock_result

    with pytest.raises(RuntimeError) as excinfo:
        event_viewer._execute_wevtutil_query("*")

    assert "アクセスが拒否されました。アプリケーションを管理者権限で実行してください。" in str(excinfo.value)

@patch('subprocess.run')
def test_execute_wevtutil_query_cp932_decode_error_fallback_to_utf8(mock_run):
    # b'\xc2\x81' is invalid in CP932 but valid in UTF-8
    mock_result = MagicMock()
    mock_result.stdout = b"\xc2\x81"
    mock_result.stderr = b""
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    # We can call the private function directly for testing
    output = event_viewer._execute_wevtutil_query("*")
    assert output == b"\xc2\x81".decode("utf-8")

@patch('subprocess.run')
def test_execute_wevtutil_query_both_decode_error_fallback_to_replace(mock_run):
    # b'\x81' is invalid in both CP932 and UTF-8
    mock_result = MagicMock()
    mock_result.stdout = b"\x81"
    mock_result.stderr = b""
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    output = event_viewer._execute_wevtutil_query("*")
    assert output == b"\x81".decode("utf-8", errors="replace")

@patch.dict(os.environ, {"SystemRoot": "D:\\WinNT"}, clear=True)
def test_get_wevtutil_path_with_systemroot():
    event_viewer.get_wevtutil_path.cache_clear()
    expected = os.path.join("D:\\WinNT", "System32", "wevtutil.exe")
    assert event_viewer.get_wevtutil_path() == expected

@patch.dict(os.environ, {}, clear=True)
def test_get_wevtutil_path_without_systemroot():
    event_viewer.get_wevtutil_path.cache_clear()
    expected = os.path.join("C:\\Windows", "System32", "wevtutil.exe")
    assert event_viewer.get_wevtutil_path() == expected
import pytest
from unittest.mock import MagicMock, patch
import tkinter as tk
import event_viewer

@pytest.mark.parametrize("start_y, start_m, delta, expected_y, expected_m", [
    (2024, 1, 1, 2024, 2),
    (2024, 1, 12, 2025, 1),
    (2024, 12, 1, 2025, 1),
    (2024, 1, -1, 2023, 12),
    (2024, 1, -12, 2023, 1),
    (2024, 12, -12, 2023, 12),
    (2024, 5, 24, 2026, 5),
    (2024, 5, -24, 2022, 5),
    (2024, 1, 100, 2032, 5),
    (2024, 1, -100, 2015, 9),
])
def test_calendar_dialog_add_months(start_y, start_m, delta, expected_y, expected_m):
    parent = tk.Tk()
    target_entry = tk.Entry(parent)
    target_entry.insert(0, f"{start_y}-{start_m:02d}-01")

    with patch('event_viewer.CalendarDialog.create_widgets'),          patch('event_viewer.CalendarDialog.update_calendar'),          patch('tkinter.Toplevel.grab_set'),          patch('tkinter.Toplevel.transient'):

        dialog = event_viewer.CalendarDialog(parent, target_entry)
        dialog.year_var.set(start_y)
        dialog.month_var.set(start_m)

        dialog.add_months(delta)

        assert dialog.year_var.get() == expected_y
        assert dialog.month_var.get() == expected_m

    parent.destroy()
