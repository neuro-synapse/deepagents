from deepagents.sub_agent import _create_task_tool, SubAgent
from deepagents.event_driven_subagent import _create_event_driven_task_tool, EventDrivenResearchOrchestrator
from deepagents.model import get_default_model
from deepagents.tools import write_todos, write_file, read_file, ls, edit_file
from deepagents.event_tools import (
    start_parallel_research, complete_research_task, write_file_with_events,
    write_todos_with_events, request_critique, get_event_status
)
from deepagents.state import DeepAgentState
from deepagents.events import get_event_bus, EventDrivenCoordinator
from typing import Sequence, Union, Callable, Any, TypeVar, Type, Optional
from langchain_core.tools import BaseTool
from langchain_core.language_models import LanguageModelLike

from langgraph.prebuilt import create_react_agent

StateSchema = TypeVar("StateSchema", bound=DeepAgentState)
StateSchemaType = Type[StateSchema]

base_prompt = """You have access to a number of standard tools

## `write_todos`

You have access to the `write_todos` tools to help you manage and plan tasks. Use these tools VERY frequently to ensure that you are tracking your tasks and giving the user visibility into your progress.
These tools are also EXTREMELY helpful for planning tasks, and for breaking down larger complex tasks into smaller steps. If you do not use this tool when planning, you may forget to do important tasks - and that is unacceptable.

It is critical that you mark todos as completed as soon as you are done with a task. Do not batch up multiple tasks before marking them as completed.
## `task`

- When doing web search, prefer to use the `task` tool in order to reduce context usage.

## Event-Driven Mode

When event_driven_mode is enabled, you have access to additional event-driven tools for parallel processing:

- `start_parallel_research`: Start research tasks that run in parallel
- `complete_research_task`: Mark research tasks as completed
- `write_file_with_events`: Write files with event emission
- `write_todos_with_events`: Update todos with event coordination
- `request_critique`: Request critique with event-driven coordination
- `get_event_status`: Check status of active tasks and events

Use the 'event-driven:' prefix in task descriptions to enable parallel processing."""


def create_deep_agent(
    tools: Sequence[Union[BaseTool, Callable, dict[str, Any]]],
    instructions: str,
    model: Optional[Union[str, LanguageModelLike]] = None,
    subagents: list[SubAgent] = None,
    state_schema: Optional[StateSchemaType] = None,
    event_driven: bool = False,
):
    """Create a deep agent.

    This agent will by default have access to a tool to write todos (write_todos),
    and then four file editing tools: write_file, ls, read_file, edit_file.

    Args:
        tools: The additional tools the agent should have access to.
        instructions: The additional instructions the agent should have. Will go in
            the system prompt.
        model: The model to use.
        subagents: The subagents to use. Each subagent should be a dictionary with the
            following keys:
                - `name`
                - `description` (used by the main agent to decide whether to call the sub agent)
                - `prompt` (used as the system prompt in the subagent)
                - (optional) `tools`
        state_schema: The schema of the deep agent. Should subclass from DeepAgentState
        event_driven: Whether to enable event-driven mode with parallel processing capabilities
    """
    prompt = instructions + base_prompt
    built_in_tools = [write_todos, write_file, read_file, ls, edit_file]
    
    if model is None:
        model = get_default_model()
    state_schema = state_schema or DeepAgentState
    
    if event_driven:
        # Add event-driven tools
        event_tools = [
            start_parallel_research, complete_research_task, write_file_with_events,
            write_todos_with_events, request_critique, get_event_status
        ]
        built_in_tools.extend(event_tools)
        
        # Use event-driven task tool
        task_tool = _create_event_driven_task_tool(
            list(tools) + built_in_tools,
            instructions,
            subagents or [],
            model,
            state_schema
        )
        
        # Initialize event-driven components
        event_bus = get_event_bus()
        coordinator = EventDrivenCoordinator(event_bus)
        orchestrator = EventDrivenResearchOrchestrator(event_bus)
    else:
        # Use regular task tool
        task_tool = _create_task_tool(
            list(tools) + built_in_tools,
            instructions,
            subagents or [],
            model,
            state_schema
        )
    
    all_tools = built_in_tools + list(tools) + [task_tool]
    
    agent = create_react_agent(
        model,
        prompt=prompt,
        tools=all_tools,
        state_schema=state_schema,
    )
    
    # Mark the agent as event-driven in the config if enabled
    if event_driven:
        # Add event_driven_mode to initial state
        original_invoke = agent.invoke
        
        def invoke_with_event_mode(input_data, *args, **kwargs):
            if isinstance(input_data, dict) and "event_driven_mode" not in input_data:
                input_data["event_driven_mode"] = True
            return original_invoke(input_data, *args, **kwargs)
        
        agent.invoke = invoke_with_event_mode
    
    return agent
