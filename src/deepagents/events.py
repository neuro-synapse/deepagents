"""Event system for event-driven deep agents.

This module provides the core event infrastructure needed to make deep agents
event-driven, enabling asynchronous and parallel processing of research tasks.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from uuid import uuid4


class EventType(Enum):
    """Standard event types for deep agents."""
    
    # Research events
    RESEARCH_REQUESTED = "research_requested"
    RESEARCH_STARTED = "research_started"
    RESEARCH_COMPLETED = "research_completed"
    RESEARCH_FAILED = "research_failed"
    
    # Critique events
    CRITIQUE_REQUESTED = "critique_requested"
    CRITIQUE_COMPLETED = "critique_completed"
    
    # File events
    FILE_CREATED = "file_created"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    
    # Todo events
    TODO_CREATED = "todo_created"
    TODO_UPDATED = "todo_updated"
    TODO_COMPLETED = "todo_completed"
    
    # Agent events
    SUBAGENT_SPAWNED = "subagent_spawned"
    SUBAGENT_COMPLETED = "subagent_completed"
    
    # Coordination events
    PARALLEL_TASK_STARTED = "parallel_task_started"
    PARALLEL_TASK_COMPLETED = "parallel_task_completed"
    ALL_TASKS_COMPLETED = "all_tasks_completed"


@dataclass
class Event:
    """Base event class for the event system."""
    
    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    source_agent: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchEvent(Event):
    """Event for research-related activities."""
    
    query: str = ""
    agent_name: str = ""
    results: Optional[str] = None
    error: Optional[str] = None


@dataclass
class FileEvent(Event):
    """Event for file system operations."""
    
    file_path: str = ""
    content: Optional[str] = None
    operation: str = ""


@dataclass
class TodoEvent(Event):
    """Event for todo list operations."""
    
    todo_id: Optional[str] = None
    content: str = ""
    status: str = ""


EventHandler = Callable[[Event], Union[None, asyncio.Future]]
EventHandlerAsync = Callable[[Event], asyncio.Future]


class EventBus:
    """Central event bus for routing events between components."""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._async_handlers: Dict[EventType, List[EventHandlerAsync]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000  # Limit memory usage
        
    def subscribe(self, event_type: EventType, handler: EventHandler):
        """Subscribe a handler to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        
    def subscribe_async(self, event_type: EventType, handler: EventHandlerAsync):
        """Subscribe an async handler to an event type."""
        if event_type not in self._async_handlers:
            self._async_handlers[event_type] = []
        self._async_handlers[event_type].append(handler)
        
    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass
                
    def emit(self, event: Event) -> List[Any]:
        """Emit an event synchronously to all registered handlers."""
        self._add_to_history(event)
        results = []
        
        # Call sync handlers
        for handler in self._handlers.get(event.event_type, []):
            try:
                result = handler(event)
                results.append(result)
            except Exception as e:
                # Log error but don't stop other handlers
                print(f"Error in event handler: {e}")
                
        return results
        
    async def emit_async(self, event: Event) -> List[Any]:
        """Emit an event asynchronously to all registered handlers."""
        self._add_to_history(event)
        results = []
        
        # Call sync handlers first
        sync_results = self.emit(event)
        results.extend(sync_results)
        
        # Call async handlers
        async_tasks = []
        for handler in self._async_handlers.get(event.event_type, []):
            task = asyncio.create_task(handler(event))
            async_tasks.append(task)
            
        if async_tasks:
            async_results = await asyncio.gather(*async_tasks, return_exceptions=True)
            results.extend(async_results)
            
        return results
        
    def _add_to_history(self, event: Event):
        """Add event to history with size limit."""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history//2:]  # Keep last half
            
    def get_events(self, 
                   event_type: Optional[EventType] = None,
                   since: Optional[datetime] = None,
                   limit: Optional[int] = None) -> List[Event]:
        """Get events from history with optional filtering."""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
            
        if since:
            events = [e for e in events if e.timestamp >= since]
            
        if limit:
            events = events[-limit:]
            
        return events
        
    def clear_history(self):
        """Clear event history."""
        self._event_history.clear()


class EventDrivenComponent(ABC):
    """Base class for components that can handle events."""
    
    def __init__(self, event_bus: EventBus, component_name: str):
        self.event_bus = event_bus
        self.component_name = component_name
        self._setup_event_handlers()
        
    @abstractmethod
    def _setup_event_handlers(self):
        """Setup event handlers for this component."""
        pass
        
    def emit_event(self, event: Event):
        """Emit an event through the event bus."""
        event.source_agent = self.component_name
        self.event_bus.emit(event)
        
    async def emit_event_async(self, event: Event):
        """Emit an event asynchronously through the event bus."""
        event.source_agent = self.component_name
        await self.event_bus.emit_async(event)


# Global event bus instance
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def set_event_bus(event_bus: EventBus):
    """Set the global event bus instance."""
    global _global_event_bus
    _global_event_bus = event_bus


class EventDrivenCoordinator(EventDrivenComponent):
    """Coordinates parallel tasks and emits completion events."""
    
    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus, "coordinator")
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        
    def _setup_event_handlers(self):
        """Setup handlers for task coordination events."""
        self.event_bus.subscribe(EventType.PARALLEL_TASK_STARTED, self._handle_task_started)
        self.event_bus.subscribe(EventType.PARALLEL_TASK_COMPLETED, self._handle_task_completed)
        
    def _handle_task_started(self, event: Event):
        """Handle parallel task started event."""
        task_group = event.data.get("task_group", "default")
        task_id = event.data.get("task_id", event.event_id)
        
        if task_group not in self._active_tasks:
            self._active_tasks[task_group] = {}
            
        self._active_tasks[task_group][task_id] = {
            "started": event.timestamp,
            "status": "running"
        }
        
    def _handle_task_completed(self, event: Event):
        """Handle parallel task completed event."""
        task_group = event.data.get("task_group", "default")
        task_id = event.data.get("task_id", event.event_id)
        
        if task_group in self._active_tasks and task_id in self._active_tasks[task_group]:
            self._active_tasks[task_group][task_id]["status"] = "completed"
            self._active_tasks[task_group][task_id]["completed"] = event.timestamp
            
            # Check if all tasks in group are completed
            group_tasks = self._active_tasks[task_group]
            if all(task["status"] == "completed" for task in group_tasks.values()):
                completion_event = Event(
                    event_type=EventType.ALL_TASKS_COMPLETED,
                    data={"task_group": task_group, "task_count": len(group_tasks)}
                )
                self.emit_event(completion_event)
                
                # Clean up completed task group
                del self._active_tasks[task_group]
    
    def get_active_tasks(self, task_group: Optional[str] = None) -> Dict[str, Any]:
        """Get currently active tasks."""
        if task_group:
            return self._active_tasks.get(task_group, {})
        return self._active_tasks.copy()