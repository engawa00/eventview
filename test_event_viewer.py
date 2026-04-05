import pytest
from unittest.mock import patch, MagicMock
import datetime
import sys

# Mock tkinter before importing event_viewer to avoid ModuleNotFoundError in environments without tkinter
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
def test_get_wake_events_error(mock_run):
    # Simulate an OS error during subprocess run
    mock_run.side_effect = Exception("Command failed")
    
    events = event_viewer.get_wake_events()
    assert len(events) == 1
    assert "error" in events[0]
    assert "Command failed" in events[0]["error"]
