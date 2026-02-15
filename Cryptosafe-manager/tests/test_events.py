from src.core.events import EventBus, ENTRY_ADDED


def test_event_bus_publish():
    bus = EventBus()
    result = []

    def handler(data):
        result.append(data)

    bus.subscribe(ENTRY_ADDED, handler)
    bus.publish(ENTRY_ADDED, {"id": 1})

    assert result[0]["id"] == 1
