"""
Integration test using mock model to verify event-driven agent creation.
"""

from unittest.mock import Mock
from deepagents import create_deep_agent
from deepagents.events import get_event_bus, EventType


def test_event_driven_agent_creation():
    """Test that we can create an event-driven agent with a mock model."""
    
    # Create a very simple mock model
    mock_model = Mock()
    mock_model.invoke = Mock(return_value="Mock response")
    
    def mock_tool(query: str):
        """Mock tool for testing purposes."""
        return f"Mock result for: {query}"
    
    # Create event-driven agent with mock model
    agent = create_deep_agent(
        tools=[mock_tool],
        instructions="You are a test agent.",
        model=mock_model,
        event_driven=True
    )
    
    print("✓ Event-driven agent created successfully with mock model")
    
    # The agent is a CompiledStateGraph, so we can't directly inspect tools
    # But we can verify it was created successfully
    assert agent is not None
    assert hasattr(agent, 'invoke')
    
    print("✓ Agent has expected interface")
    
    return True


def test_subagent_configuration():
    """Test creating event-driven agent with subagents."""
    
    mock_model = Mock()
    mock_model.invoke = Mock(return_value="Mock response")
    
    def mock_search(query: str):
        """Mock search tool for testing."""
        return {"results": [{"title": "Mock", "content": "Mock content"}]}
    
    research_subagent = {
        "name": "research-agent",
        "description": "Conducts research",
        "prompt": "You are a researcher.",
        "tools": ["mock_search"]
    }
    
    agent = create_deep_agent(
        tools=[mock_search],
        instructions="You are a research coordinator.",
        model=mock_model,
        subagents=[research_subagent],
        event_driven=True
    )
    
    print("✓ Event-driven agent with subagents created successfully")
    return True


def test_event_bus_integration():
    """Test that event bus is properly initialized."""
    
    # Clear any existing event bus state
    event_bus = get_event_bus()
    event_bus.clear_history()
    
    events_received = []
    
    def test_handler(event):
        events_received.append(event)
    
    event_bus.subscribe(EventType.RESEARCH_REQUESTED, test_handler)
    
    # Create agent which should use the global event bus
    mock_model = Mock()
    agent = create_deep_agent(
        tools=[],
        instructions="Test agent",
        model=mock_model,
        event_driven=True
    )
    
    print("✓ Event bus integration working")
    
    # Verify we can emit events
    from deepagents.events import ResearchEvent
    test_event = ResearchEvent(
        event_type=EventType.RESEARCH_REQUESTED,
        query="test",
        agent_name="test"
    )
    
    event_bus.emit(test_event)
    
    assert len(events_received) == 1
    print("✓ Event emission and handling working")
    
    return True


def run_integration_tests():
    """Run all integration tests."""
    print("Running Event-Driven Integration Tests")
    print("=" * 50)
    
    tests = [
        test_event_driven_agent_creation,
        test_subagent_configuration,
        test_event_bus_integration,
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
    success = run_integration_tests()
    exit(0 if success else 1)