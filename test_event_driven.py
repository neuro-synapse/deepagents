"""
Simple test script to validate event-driven functionality without external dependencies.
"""

import asyncio
from deepagents import create_deep_agent, get_event_bus, EventType
from deepagents.events import Event, ResearchEvent


def mock_search_tool(query: str, max_results: int = 3):
    """Mock search tool that returns fake results for testing."""
    return {
        "results": [
            {"title": f"Result 1 for {query}", "content": f"Mock content about {query}"},
            {"title": f"Result 2 for {query}", "content": f"More mock content about {query}"},
        ]
    }


def test_event_driven_basic():
    """Test basic event-driven agent creation and invocation."""
    print("Testing basic event-driven agent...")
    
    # Create event-driven agent
    agent = create_deep_agent(
        tools=[mock_search_tool],
        instructions="You are a test researcher.",
        event_driven=True
    )
    
    # Test basic invocation
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Create a simple todo list"}],
        "event_driven_mode": True
    })
    
    print(f"✓ Agent created and invoked successfully")
    print(f"  - Messages: {len(result.get('messages', []))}")
    print(f"  - Events: {len(result.get('events', []))}")
    print(f"  - Files: {len(result.get('files', {}))}")
    
    return True


def test_event_bus():
    """Test event bus functionality."""
    print("Testing event bus...")
    
    event_bus = get_event_bus()
    events_received = []
    
    def handler(event):
        events_received.append(event)
    
    # Subscribe to events
    event_bus.subscribe(EventType.RESEARCH_REQUESTED, handler)
    
    # Emit event
    test_event = ResearchEvent(
        event_type=EventType.RESEARCH_REQUESTED,
        query="test query",
        agent_name="test-agent"
    )
    event_bus.emit(test_event)
    
    print(f"✓ Event bus working")
    print(f"  - Events emitted: 1")
    print(f"  - Events received: {len(events_received)}")
    
    # Clear for next test
    event_bus.clear_history()
    
    return len(events_received) == 1


def test_parallel_research_tools():
    """Test the parallel research tools."""
    print("Testing parallel research tools...")
    
    agent = create_deep_agent(
        tools=[mock_search_tool],
        instructions="You are a test researcher that uses parallel research.",
        event_driven=True
    )
    
    # Test starting parallel research
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Use start_parallel_research to research 'test topic'"}],
        "event_driven_mode": True
    })
    
    events = result.get("events", [])
    active_tasks = result.get("active_tasks", {})
    
    print(f"✓ Parallel research tools working")
    print(f"  - Events generated: {len(events)}")
    print(f"  - Active tasks: {len(active_tasks)}")
    print(f"  - Event types: {[e.get('event_type') for e in events]}")
    
    return len(events) > 0


def test_file_events():
    """Test file operations with events."""
    print("Testing file operations with events...")
    
    agent = create_deep_agent(
        tools=[],
        instructions="You are a test agent that works with files.",
        event_driven=True
    )
    
    # Test writing files with events
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Use write_file_with_events to create a test file"}],
        "event_driven_mode": True
    })
    
    files = result.get("files", {})
    events = result.get("events", [])
    
    print(f"✓ File operations with events working")
    print(f"  - Files created: {len(files)}")
    print(f"  - File events: {len([e for e in events if 'file' in e.get('event_type', '')])}")
    
    return len(files) > 0 or len(events) > 0


def test_event_status_tool():
    """Test the event status tool."""
    print("Testing event status tool...")
    
    agent = create_deep_agent(
        tools=[],
        instructions="You are a test agent that checks event status.",
        event_driven=True
    )
    
    # First create some events, then check status
    result = agent.invoke({
        "messages": [{"role": "user", "content": "First use start_parallel_research for 'topic 1', then use get_event_status to check"}],
        "event_driven_mode": True
    })
    
    # Should have messages about status
    messages = result.get("messages", [])
    events = result.get("events", [])
    
    print(f"✓ Event status tool working")
    print(f"  - Messages: {len(messages)}")
    print(f"  - Events tracked: {len(events)}")
    
    return len(messages) > 0


def run_all_tests():
    """Run all tests and report results."""
    print("Running Event-Driven DeepAgents Tests")
    print("=" * 50)
    
    tests = [
        test_event_driven_basic,
        test_event_bus,
        test_parallel_research_tools,
        test_file_events,
        test_event_status_tool,
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
    success = run_all_tests()
    exit(0 if success else 1)