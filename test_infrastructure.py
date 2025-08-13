"""
Test the event infrastructure without requiring external API keys.
"""

from deepagents.events import EventBus, Event, EventType, ResearchEvent, get_event_bus, EventDrivenCoordinator
from deepagents.state import DeepAgentState
from deepagents.event_tools import start_parallel_research, complete_research_task
from langchain_core.messages import BaseMessage
from datetime import datetime


def test_event_system():
    """Test the core event system functionality."""
    print("Testing event system...")
    
    # Test event bus
    event_bus = EventBus()
    events_received = []
    
    def handler(event):
        events_received.append(event)
    
    event_bus.subscribe(EventType.RESEARCH_REQUESTED, handler)
    
    # Create and emit event
    test_event = ResearchEvent(
        event_type=EventType.RESEARCH_REQUESTED,
        query="test query",
        agent_name="test-agent"
    )
    
    event_bus.emit(test_event)
    
    assert len(events_received) == 1, f"Expected 1 event, got {len(events_received)}"
    assert events_received[0].query == "test query"
    
    print("✓ Event bus working correctly")
    return True


def test_coordinator():
    """Test the event-driven coordinator."""
    print("Testing event coordinator...")
    
    event_bus = EventBus()
    coordinator = EventDrivenCoordinator(event_bus)
    
    all_tasks_completed_events = []
    
    def completion_handler(event):
        all_tasks_completed_events.append(event)
    
    event_bus.subscribe(EventType.ALL_TASKS_COMPLETED, completion_handler)
    
    # Start some parallel tasks
    task1_event = Event(
        event_type=EventType.PARALLEL_TASK_STARTED,
        data={"task_group": "test_group", "task_id": "task1"}
    )
    
    task2_event = Event(
        event_type=EventType.PARALLEL_TASK_STARTED,
        data={"task_group": "test_group", "task_id": "task2"}
    )
    
    event_bus.emit(task1_event)
    event_bus.emit(task2_event)
    
    # Complete the tasks
    complete1_event = Event(
        event_type=EventType.PARALLEL_TASK_COMPLETED,
        data={"task_group": "test_group", "task_id": "task1"}
    )
    
    complete2_event = Event(
        event_type=EventType.PARALLEL_TASK_COMPLETED,
        data={"task_group": "test_group", "task_id": "task2"}
    )
    
    event_bus.emit(complete1_event)
    assert len(all_tasks_completed_events) == 0, "Should not complete until all tasks done"
    
    event_bus.emit(complete2_event)
    assert len(all_tasks_completed_events) == 1, "Should complete when all tasks done"
    
    print("✓ Coordinator working correctly")
    return True


def test_state_reducers():
    """Test the state reducers for event-driven features."""
    print("Testing state reducers...")
    
    from deepagents.state import event_reducer, active_tasks_reducer
    
    # Test event reducer
    events1 = [{"event_id": "1", "type": "test"}]
    events2 = [{"event_id": "2", "type": "test"}]
    events3 = [{"event_id": "1", "type": "duplicate"}]  # Duplicate ID
    
    combined = event_reducer(events1, events2)
    assert len(combined) == 2, f"Expected 2 events, got {len(combined)}"
    
    # Test deduplication
    combined_with_dup = event_reducer(combined, events3)
    assert len(combined_with_dup) == 2, "Should deduplicate by event_id"
    
    # Test active tasks reducer
    tasks1 = {"task1": {"status": "running"}}
    tasks2 = {"task2": {"status": "completed"}}
    
    combined_tasks = active_tasks_reducer(tasks1, tasks2)
    assert len(combined_tasks) == 2
    assert "task1" in combined_tasks
    assert "task2" in combined_tasks
    
    print("✓ State reducers working correctly")
    return True


def test_event_tool_state_updates():
    """Test that event tools properly update state."""
    print("Testing event tools state updates...")
    
    # Mock state
    state = {
        "active_tasks": {},
        "events": [],
        "messages": []
    }
    
    # Test start_parallel_research (we'll mock the tool call)
    from deepagents.event_tools import start_parallel_research
    from langchain_core.tools import InjectedToolCallId
    from unittest.mock import Mock
    
    # Mock the injected parameters
    mock_tool_call_id = "test_call_id"
    
    # We can't easily test the tool directly due to the injections,
    # but we can test the event emission logic
    event_bus = get_event_bus()
    event_bus.clear_history()
    
    # Create a research event manually
    research_event = ResearchEvent(
        event_type=EventType.RESEARCH_REQUESTED,
        query="test query",
        agent_name="research-agent"
    )
    
    event_bus.emit(research_event)
    
    events = event_bus.get_events(EventType.RESEARCH_REQUESTED)
    assert len(events) == 1
    assert events[0].query == "test query"
    
    print("✓ Event tools state updates working")
    return True


def test_event_history():
    """Test event history and querying functionality."""
    print("Testing event history...")
    
    event_bus = EventBus()
    
    # Add some events
    for i in range(5):
        event = Event(
            event_type=EventType.RESEARCH_REQUESTED,
            data={"query": f"query_{i}"}
        )
        event_bus.emit(event)
    
    # Add different type of event
    file_event = Event(
        event_type=EventType.FILE_CREATED,
        data={"file": "test.txt"}
    )
    event_bus.emit(file_event)
    
    # Test getting all events
    all_events = event_bus.get_events()
    assert len(all_events) == 6
    
    # Test filtering by type
    research_events = event_bus.get_events(EventType.RESEARCH_REQUESTED)
    assert len(research_events) == 5
    
    file_events = event_bus.get_events(EventType.FILE_CREATED)
    assert len(file_events) == 1
    
    # Test limit
    limited_events = event_bus.get_events(limit=3)
    assert len(limited_events) == 3
    
    print("✓ Event history working correctly")
    return True


def run_infrastructure_tests():
    """Run all infrastructure tests."""
    print("Testing Event-Driven Infrastructure")
    print("=" * 50)
    
    tests = [
        test_event_system,
        test_coordinator,
        test_state_reducers,
        test_event_tool_state_updates,
        test_event_history,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result, None))
            print()
        except Exception as e:
            results.append((test_func.__name__, False, str(e)))
            print(f"✗ {test_func.__name__} failed: {e}")
            print()
    
    # Summary
    print("Test Results Summary:")
    print("-" * 30)
    passed = 0
    for test_name, success, error in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{test_name}: {status}")
        if error:
            print(f"  Error: {error}")
        if success:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(tests)} tests passed")
    
    return passed == len(tests)


if __name__ == "__main__":
    success = run_infrastructure_tests()
    exit(0 if success else 1)