"""Event-driven tools for deep agents.

These tools extend the base functionality with event emission capabilities,
enabling asynchronous and parallel processing in event-driven agents.
"""

import asyncio
from datetime import datetime
from typing import Annotated, Dict, Any, Optional, List
from uuid import uuid4

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from langgraph.prebuilt import InjectedState

from deepagents.state import DeepAgentState, Todo
from deepagents.events import (
    Event, EventType, ResearchEvent, FileEvent, TodoEvent,
    get_event_bus
)


@tool(description="Start a parallel research task that will run asynchronously and emit events when complete.")
def start_parallel_research(
    query: str,
    agent_name: str = "research-agent",
    task_group: str = "default",
    priority: int = 1,
    state: Annotated[DeepAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Start a parallel research task that runs asynchronously."""
    task_id = str(uuid4())
    
    # Emit task started event
    event_bus = get_event_bus()
    start_event = Event(
        event_type=EventType.PARALLEL_TASK_STARTED,
        data={
            "task_id": task_id,
            "task_group": task_group,
            "query": query,
            "agent_name": agent_name,
            "priority": priority
        }
    )
    event_bus.emit(start_event)
    
    # Emit research requested event
    research_event = ResearchEvent(
        event_type=EventType.RESEARCH_REQUESTED,
        query=query,
        agent_name=agent_name,
        data={
            "task_id": task_id,
            "task_group": task_group,
            "priority": priority
        }
    )
    event_bus.emit(research_event)
    
    # Update state with active task
    active_tasks = state.get("active_tasks", {})
    active_tasks[task_id] = {
        "query": query,
        "agent_name": agent_name,
        "task_group": task_group,
        "priority": priority,
        "status": "started",
        "started_at": datetime.now().isoformat()
    }
    
    # Add event to state
    events = state.get("events", [])
    events.extend([
        {
            "event_type": start_event.event_type.value,
            "event_id": start_event.event_id,
            "timestamp": start_event.timestamp.isoformat(),
            "data": start_event.data
        },
        {
            "event_type": research_event.event_type.value,
            "event_id": research_event.event_id,
            "timestamp": research_event.timestamp.isoformat(),
            "data": research_event.data,
            "query": query,
            "agent_name": agent_name
        }
    ])
    
    return Command(
        update={
            "active_tasks": active_tasks,
            "events": events,
            "messages": [
                ToolMessage(
                    f"Started parallel research task '{query}' with ID {task_id} in group '{task_group}'",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )


@tool(description="Complete a research task and emit completion events.")
def complete_research_task(
    task_id: str,
    results: str,
    agent_name: str = "research-agent",
    state: Annotated[DeepAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Complete a research task and emit relevant events."""
    
    # Get task info from active tasks
    active_tasks = state.get("active_tasks", {})
    if task_id not in active_tasks:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error: Task ID {task_id} not found in active tasks",
                        tool_call_id=tool_call_id
                    )
                ]
            }
        )
    
    task_info = active_tasks[task_id]
    task_group = task_info.get("task_group", "default")
    
    # Emit research completed event
    event_bus = get_event_bus()
    research_event = ResearchEvent(
        event_type=EventType.RESEARCH_COMPLETED,
        query=task_info.get("query", ""),
        agent_name=agent_name,
        results=results,
        data={
            "task_id": task_id,
            "task_group": task_group
        }
    )
    event_bus.emit(research_event)
    
    # Emit parallel task completed event
    completion_event = Event(
        event_type=EventType.PARALLEL_TASK_COMPLETED,
        data={
            "task_id": task_id,
            "task_group": task_group,
            "results": results
        }
    )
    event_bus.emit(completion_event)
    
    # Update active tasks
    task_info["status"] = "completed"
    task_info["completed_at"] = datetime.now().isoformat()
    task_info["results"] = results
    
    # Add events to state
    events = state.get("events", [])
    events.extend([
        {
            "event_type": research_event.event_type.value,
            "event_id": research_event.event_id,
            "timestamp": research_event.timestamp.isoformat(),
            "data": research_event.data,
            "query": research_event.query,
            "agent_name": research_event.agent_name,
            "results": research_event.results
        },
        {
            "event_type": completion_event.event_type.value,
            "event_id": completion_event.event_id,
            "timestamp": completion_event.timestamp.isoformat(),
            "data": completion_event.data
        }
    ])
    
    return Command(
        update={
            "active_tasks": active_tasks,
            "events": events,
            "messages": [
                ToolMessage(
                    f"Completed research task {task_id}: {results[:100]}{'...' if len(results) > 100 else ''}",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )


@tool(description="Create or update a file with event emission.")
def write_file_with_events(
    file_path: str,
    content: str,
    operation: str = "write",
    state: Annotated[DeepAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Write to a file and emit file events."""
    
    files = state.get("files", {})
    is_new_file = file_path not in files
    files[file_path] = content
    
    # Determine event type
    if is_new_file:
        event_type = EventType.FILE_CREATED
        message = f"Created file {file_path}"
    else:
        event_type = EventType.FILE_UPDATED
        message = f"Updated file {file_path}"
    
    # Emit file event
    event_bus = get_event_bus()
    file_event = FileEvent(
        event_type=event_type,
        file_path=file_path,
        content=content,
        operation=operation
    )
    event_bus.emit(file_event)
    
    # Add event to state
    events = state.get("events", [])
    events.append({
        "event_type": file_event.event_type.value,
        "event_id": file_event.event_id,
        "timestamp": file_event.timestamp.isoformat(),
        "data": file_event.data,
        "file_path": file_event.file_path,
        "operation": file_event.operation
    })
    
    return Command(
        update={
            "files": files,
            "events": events,
            "messages": [ToolMessage(message, tool_call_id=tool_call_id)]
        }
    )


@tool(description="Update todos with event emission for event-driven coordination.")
def write_todos_with_events(
    todos: List[Todo],
    state: Annotated[DeepAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Write todos and emit events for each todo change."""
    
    current_todos = state.get("todos", [])
    events = state.get("events", [])
    event_bus = get_event_bus()
    
    # Process each todo and emit appropriate events
    for todo in todos:
        # Add ID if not present
        if "id" not in todo:
            todo["id"] = str(uuid4())
        
        # Check if this is a new todo or update
        existing_todo = next((t for t in current_todos if t.get("id") == todo["id"]), None)
        
        if existing_todo is None:
            # New todo
            event_type = EventType.TODO_CREATED
            todo["created_at"] = datetime.now().isoformat()
        else:
            # Updated todo
            if existing_todo["status"] != todo["status"]:
                if todo["status"] == "completed":
                    event_type = EventType.TODO_COMPLETED
                else:
                    event_type = EventType.TODO_UPDATED
            else:
                event_type = EventType.TODO_UPDATED
        
        todo["updated_at"] = datetime.now().isoformat()
        
        # Emit todo event
        todo_event = TodoEvent(
            event_type=event_type,
            todo_id=todo["id"],
            content=todo["content"],
            status=todo["status"]
        )
        event_bus.emit(todo_event)
        
        # Add event to state
        events.append({
            "event_type": todo_event.event_type.value,
            "event_id": todo_event.event_id,
            "timestamp": todo_event.timestamp.isoformat(),
            "data": todo_event.data,
            "todo_id": todo_event.todo_id,
            "content": todo_event.content,
            "status": todo_event.status
        })
    
    return Command(
        update={
            "todos": todos,
            "events": events,
            "messages": [
                ToolMessage(f"Updated todo list to {todos}", tool_call_id=tool_call_id)
            ]
        }
    )


@tool(description="Request critique of a document with event-driven coordination.")
def request_critique(
    document_path: str,
    critique_instructions: str = "",
    task_group: str = "critique",
    state: Annotated[DeepAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Request critique of a document and emit critique events."""
    
    task_id = str(uuid4())
    
    # Emit critique requested event
    event_bus = get_event_bus()
    critique_event = Event(
        event_type=EventType.CRITIQUE_REQUESTED,
        data={
            "task_id": task_id,
            "task_group": task_group,
            "document_path": document_path,
            "instructions": critique_instructions
        }
    )
    event_bus.emit(critique_event)
    
    # Update active tasks
    active_tasks = state.get("active_tasks", {})
    active_tasks[task_id] = {
        "type": "critique",
        "document_path": document_path,
        "instructions": critique_instructions,
        "task_group": task_group,
        "status": "requested",
        "started_at": datetime.now().isoformat()
    }
    
    # Add event to state
    events = state.get("events", [])
    events.append({
        "event_type": critique_event.event_type.value,
        "event_id": critique_event.event_id,
        "timestamp": critique_event.timestamp.isoformat(),
        "data": critique_event.data
    })
    
    return Command(
        update={
            "active_tasks": active_tasks,
            "events": events,
            "messages": [
                ToolMessage(
                    f"Requested critique of {document_path} with task ID {task_id}",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )


@tool(description="Get status of active tasks and recent events.")
def get_event_status(
    task_group: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 10,
    state: Annotated[DeepAgentState, InjectedState] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = None,
) -> Command:
    """Get status of active tasks and recent events."""
    
    active_tasks = state.get("active_tasks", {})
    events = state.get("events", [])
    
    # Filter active tasks by group if specified
    if task_group:
        filtered_tasks = {k: v for k, v in active_tasks.items() 
                         if v.get("task_group") == task_group}
    else:
        filtered_tasks = active_tasks
    
    # Filter events by type if specified
    if event_type:
        filtered_events = [e for e in events if e.get("event_type") == event_type]
    else:
        filtered_events = events
    
    # Get recent events
    recent_events = filtered_events[-limit:]
    
    status_report = {
        "active_tasks": filtered_tasks,
        "recent_events": recent_events,
        "total_active_tasks": len(filtered_tasks),
        "total_events": len(filtered_events)
    }
    
    return Command(
        update={
            "messages": [
                ToolMessage(
                    f"Event Status: {len(filtered_tasks)} active tasks, {len(filtered_events)} total events. "
                    f"Recent events: {[e.get('event_type') for e in recent_events]}",
                    tool_call_id=tool_call_id
                )
            ]
        }
    )