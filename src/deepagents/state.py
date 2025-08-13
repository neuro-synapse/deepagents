from langgraph.prebuilt.chat_agent_executor import AgentState
from typing import NotRequired, Annotated, List, Dict, Any
from typing import Literal
from typing_extensions import TypedDict


class Todo(TypedDict):
    """Todo to track."""

    content: str
    status: Literal["pending", "in_progress", "completed"]
    id: NotRequired[str]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]


def file_reducer(l, r):
    if l is None:
        return r
    elif r is None:
        return l
    else:
        return {**l, **r}


def event_reducer(l, r):
    """Reducer for event lists that maintains order and prevents duplicates."""
    if l is None:
        return r or []
    elif r is None:
        return l or []
    else:
        # Combine lists and deduplicate by event_id
        combined = (l or []) + (r or [])
        seen = set()
        result = []
        for event in combined:
            event_id = event.get('event_id') if isinstance(event, dict) else getattr(event, 'event_id', None)
            if event_id and event_id not in seen:
                seen.add(event_id)
                result.append(event)
        return result


def active_tasks_reducer(l, r):
    """Reducer for active tasks that merges dictionaries."""
    if l is None:
        return r or {}
    elif r is None:
        return l or {}
    else:
        return {**(l or {}), **(r or {})}


class DeepAgentState(AgentState):
    todos: NotRequired[list[Todo]]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]
    # Event-driven features
    events: Annotated[NotRequired[List[Dict[str, Any]]], event_reducer]
    active_tasks: Annotated[NotRequired[Dict[str, Any]], active_tasks_reducer]
    research_context: NotRequired[Dict[str, Any]]
    event_driven_mode: NotRequired[bool]
