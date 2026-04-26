import timeit
import xml.etree.ElementTree as ET
from typing import List, Dict

# Sample XML data similar to what wevtutil might produce, but repeated many times
def generate_xml(n: int) -> str:
    event_template = """
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
    </Event>"""
    return f"<Events>{event_template * n}</Events>"

xml_doc_large = generate_xml(1000)
ns = {"win": "http://schemas.microsoft.com/win/2004/08/events/event"}
root = ET.fromstring(xml_doc_large)
events = root.findall("win:Event", ns)

def original_loop():
    data_paths = (
        "win:EventData",
        "{http://schemas.microsoft.com/win/2004/08/events/event}EventData",
        "EventData",
    )
    results = []
    for event in events:
        event_data = next(
            (node for p in data_paths if (node := event.find(p, ns)) is not None),
            None,
        )
        if event_data is not None:
            results.append(event_data)
    return results

def optimized_loop():
    data_paths = (
        "win:EventData",
        "{http://schemas.microsoft.com/win/2004/08/events/event}EventData",
        "EventData",
    )
    results = []

    # Pre-determine the correct path
    found_path = None
    if events:
        for p in data_paths:
            if events[0].find(p, ns) is not None:
                found_path = p
                break

    if found_path:
        for event in events:
            event_data = event.find(found_path, ns)
            if event_data is not None:
                results.append(event_data)
    else:
        # Fallback or just empty
        pass
    return results

if __name__ == "__main__":
    print(f"Original: {timeit.timeit(original_loop, number=100)}s")
    print(f"Optimized: {timeit.timeit(optimized_loop, number=100)}s")
