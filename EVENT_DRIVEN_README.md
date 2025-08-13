# Event-Driven Deep Agents

This document explains the event-driven features added to deepagents, enabling asynchronous and parallel processing for research workflows.

## Overview

The event-driven architecture allows deep agents to:
- Execute multiple research tasks in parallel
- Automatically coordinate between different research phases
- React to intermediate results immediately
- Scale research workflows efficiently

## Key Components

### Event System

The event system provides the foundation for event-driven coordination:

```python
from deepagents import EventType, get_event_bus

# Get the global event bus
event_bus = get_event_bus()

# Subscribe to events
def handle_research_complete(event):
    print(f"Research completed: {event.results}")

event_bus.subscribe(EventType.RESEARCH_COMPLETED, handle_research_complete)
```

### Event Types

Standard events include:
- `RESEARCH_REQUESTED` - Research task requested
- `RESEARCH_STARTED` - Research task started
- `RESEARCH_COMPLETED` - Research task completed  
- `RESEARCH_FAILED` - Research task failed
- `CRITIQUE_REQUESTED` - Critique requested
- `CRITIQUE_COMPLETED` - Critique completed
- `FILE_CREATED` / `FILE_UPDATED` - File operations
- `TODO_CREATED` / `TODO_UPDATED` / `TODO_COMPLETED` - Todo operations
- `PARALLEL_TASK_STARTED` / `PARALLEL_TASK_COMPLETED` - Parallel task coordination
- `ALL_TASKS_COMPLETED` - All tasks in a group completed

### Event-Driven Agent Creation

Create an event-driven agent by setting `event_driven=True`:

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    tools=[your_tools],
    instructions="Your agent instructions",
    subagents=[your_subagents],
    event_driven=True  # Enable event-driven mode
)
```

## Event-Driven Tools

### Parallel Research

Start research tasks that run in parallel:

```python
# In your agent prompt, use:
# start_parallel_research("economic impact of AI", "research-agent", "main_research")
# start_parallel_research("social implications of AI", "research-agent", "main_research") 
# start_parallel_research("technical aspects of AI", "research-agent", "main_research")
```

### Task Coordination

Monitor and coordinate parallel tasks:

```python
# Check status of active tasks
# get_event_status(task_group="main_research")

# Complete research tasks (done automatically by subagents)
# complete_research_task(task_id, results, agent_name)
```

### File Operations with Events

File operations that emit events for coordination:

```python
# write_file_with_events("report.md", content)  # Emits FILE_CREATED/FILE_UPDATED
# request_critique("report.md", "Check for accuracy")  # Emits CRITIQUE_REQUESTED
```

## Research Agent Example

Here's how to create an event-driven research agent:

```python
import os
from deepagents import create_deep_agent

def internet_search(query: str, max_results: int = 5):
    """Your search implementation"""
    pass

research_instructions = '''You are an expert researcher operating in EVENT-DRIVEN mode.

## Event-Driven Research Workflow:

1. Record the question: write to `question.txt`
2. Plan parallel research: break into multiple `start_parallel_research` tasks
3. Monitor progress: use `get_event_status` to check task completion
4. Generate reports: use `write_file_with_events` for automatic coordination
5. Request critique: use `request_critique` for automatic feedback

## Parallel Research Strategy:

Instead of sequential research, use parallel tasks:

start_parallel_research("economic impact of topic", "research-agent", "main_research")
start_parallel_research("social implications of topic", "research-agent", "main_research")
start_parallel_research("technical aspects of topic", "research-agent", "main_research")

Then monitor with get_event_status(task_group="main_research").
'''

research_sub_agent = {
    "name": "research-agent",
    "description": "Conducts parallel research on specific topics",
    "prompt": "You are a researcher. Conduct thorough research and provide detailed findings.",
    "tools": ["internet_search"]
}

critique_sub_agent = {
    "name": "critique-agent",
    "description": "Provides automatic critique of research reports",
    "prompt": "You critique research reports for completeness and accuracy.",
}

# Create event-driven agent
agent = create_deep_agent(
    [internet_search],
    research_instructions,
    subagents=[research_sub_agent, critique_sub_agent],
    event_driven=True
).with_config({"recursion_limit": 1000})

# Use the agent
result = agent.invoke({
    "messages": [{"role": "user", "content": "Research the future of renewable energy"}],
    "event_driven_mode": True
})

print(f"Files created: {result.get('files', {}).keys()}")
print(f"Events generated: {len(result.get('events', []))}")
print(f"Active tasks: {result.get('active_tasks', {})}")
```

## State Management

Event-driven agents have extended state:

```python
class DeepAgentState(AgentState):
    # Original state
    todos: NotRequired[list[Todo]]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]
    
    # Event-driven additions  
    events: Annotated[NotRequired[List[Dict[str, Any]]], event_reducer]
    active_tasks: Annotated[NotRequired[Dict[str, Any]], active_tasks_reducer]
    research_context: NotRequired[Dict[str, Any]]
    event_driven_mode: NotRequired[bool]
```

## Benefits

The event-driven architecture provides:

1. **Parallel Processing**: Multiple research queries run simultaneously
2. **Automatic Coordination**: Events trigger follow-up actions automatically
3. **Responsive**: React to intermediate findings immediately
4. **Scalable**: Better performance for complex research workflows
5. **Separation of Concerns**: Clear boundaries between research phases

## Backward Compatibility

Event-driven mode is completely optional. Existing agents continue to work unchanged:

```python
# Traditional synchronous agent (unchanged)
traditional_agent = create_deep_agent(
    tools, instructions, subagents,
    event_driven=False  # or omit (defaults to False)
)

# New event-driven agent
event_driven_agent = create_deep_agent(
    tools, instructions, subagents,
    event_driven=True  # Enable new capabilities
)
```

## Advanced Usage

### Custom Event Handlers

You can create custom event handlers for specific coordination logic:

```python
from deepagents import get_event_bus, EventType

event_bus = get_event_bus()

def custom_research_handler(event):
    if event.agent_name == "my-special-agent":
        # Custom logic for specific agent
        print(f"Special handling for: {event.query}")

event_bus.subscribe(EventType.RESEARCH_COMPLETED, custom_research_handler)
```

### Event-Driven Subagents

Create subagents that respond to events:

```python
from deepagents.event_driven_subagent import EventDrivenSubAgent

# This is handled automatically when event_driven=True
# But you can also create custom event-driven subagents
```

### Research Orchestration

The system includes automatic orchestration for complex research workflows:

```python
from deepagents.event_driven_subagent import EventDrivenResearchOrchestrator

# Automatically created with event-driven agents
# Coordinates between research completion, report generation, and critique
```

## Migration Guide

To convert an existing research agent to event-driven:

1. **Enable event-driven mode**:
   ```python
   agent = create_deep_agent(..., event_driven=True)
   ```

2. **Update agent instructions** to use parallel research:
   ```python
   instructions = """
   Use start_parallel_research for multiple research queries instead of sequential task calls.
   Use get_event_status to monitor progress.
   Use write_file_with_events instead of write_file for coordination.
   """
   ```

3. **Test with event status**:
   ```python
   result = agent.invoke({"messages": [...], "event_driven_mode": True})
   print(f"Events: {len(result.get('events', []))}")
   ```

The event-driven system is designed to enhance research workflows while maintaining full backward compatibility with existing agents.