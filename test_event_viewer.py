import pytest
from unittest.mock import patch, MagicMock
import datetime
import sys

# Mock tkinter before importing event_viewer to avoid ModuleNotFoundError in environments without tkinter
try:
    import tkinter
    import tkinter.ttk
    import tkinter.messagebox
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
    """
    mock_result = MagicMock()
    # Mocking stdout output with utf-8 payload
    mock_result.stdout = xml_data.encode('utf-8')
    mock_run.return_value = mock_result
    
    events = event_viewer.get_wake_events()
    assert len(events) == 2
    
    # Check first event
    assert events[0]["Reason"] == "Network Adapter"
    
    # Check second event (Empty WakeSourceText fallback to type 1 -> Power Button)
    assert events[1]["Reason"] == "電源ボタン (Power Button)"

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
