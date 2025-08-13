"""Event-driven subagent system for deep agents.

This module provides event-driven versions of subagents that can work
asynchronously and emit events for coordination.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Annotated
from uuid import uuid4

from langchain_core.tools import BaseTool, tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langchain_core.language_models import LanguageModelLike
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from langgraph.prebuilt import InjectedState

from deepagents.state import DeepAgentState
from deepagents.sub_agent import SubAgent
from deepagents.events import (
    Event, EventType, ResearchEvent, get_event_bus, EventDrivenComponent, FileEvent
)
from deepagents.prompts import TASK_DESCRIPTION_PREFIX, TASK_DESCRIPTION_SUFFIX


class EventDrivenSubAgent(EventDrivenComponent):
    """Event-driven version of a subagent that can work asynchronously."""
    
    def __init__(self, 
                 config: SubAgent,
                 tools: List[Union[BaseTool, callable]],
                 model: LanguageModelLike,
                 state_schema,
                 event_bus=None):
        super().__init__(event_bus or get_event_bus(), config["name"])
        self.config = config
        self.tools = tools
        self.model = model
        self.state_schema = state_schema
        
        # Create the actual agent
        tools_by_name = {}
        for tool_ in tools:
            if not isinstance(tool_, BaseTool):
                tool_ = tool(tool_)
            tools_by_name[tool_.name] = tool_
            
        agent_tools = tools
        if "tools" in config:
            agent_tools = [tools_by_name[t] for t in config["tools"]]
            
        self.agent = create_react_agent(
            model, 
            prompt=config["prompt"], 
            tools=agent_tools, 
            state_schema=state_schema
        )
        
    def _setup_event_handlers(self):
        """Setup event handlers for this subagent."""
        self.event_bus.subscribe(EventType.RESEARCH_REQUESTED, self._handle_research_request)
        self.event_bus.subscribe(EventType.CRITIQUE_REQUESTED, self._handle_critique_request)
        
    def _handle_research_request(self, event: Event):
        """Handle research request events."""
        if isinstance(event, ResearchEvent) and event.agent_name == self.component_name:
            # Start async research task
            asyncio.create_task(self._perform_research(event))
            
    def _handle_critique_request(self, event: Event):
        """Handle critique request events."""
        if (event.event_type == EventType.CRITIQUE_REQUESTED and 
            self.component_name == "critique-agent"):
            # Start async critique task
            asyncio.create_task(self._perform_critique(event))
    
    async def _perform_research(self, event: ResearchEvent):
        """Perform research asynchronously and emit completion events."""
        try:
            # Emit research started event
            start_event = ResearchEvent(
                event_type=EventType.RESEARCH_STARTED,
                query=event.query,
                agent_name=self.component_name,
                data=event.data
            )
            await self.emit_event_async(start_event)
            
            # Create state for the subagent
            research_state = {
                "messages": [{"role": "user", "content": event.query}]
            }
            
            # Invoke the agent
            result = self.agent.invoke(research_state)
            
            # Extract results
            results = result["messages"][-1].content if result.get("messages") else ""
            
            # Emit research completed event
            completion_event = ResearchEvent(
                event_type=EventType.RESEARCH_COMPLETED,
                query=event.query,
                agent_name=self.component_name,
                results=results,
                data=event.data
            )
            await self.emit_event_async(completion_event)
            
            # Also emit parallel task completion if this was part of a task group
            if "task_id" in event.data:
                task_completion_event = Event(
                    event_type=EventType.PARALLEL_TASK_COMPLETED,
                    data={
                        "task_id": event.data["task_id"],
                        "task_group": event.data.get("task_group", "default"),
                        "results": results,
                        "agent_name": self.component_name
                    }
                )
                await self.emit_event_async(task_completion_event)
                
        except Exception as e:
            # Emit research failed event
            error_event = ResearchEvent(
                event_type=EventType.RESEARCH_FAILED,
                query=event.query,
                agent_name=self.component_name,
                error=str(e),
                data=event.data
            )
            await self.emit_event_async(error_event)
    
    async def _perform_critique(self, event: Event):
        """Perform critique asynchronously and emit completion events."""
        try:
            document_path = event.data.get("document_path", "")
            instructions = event.data.get("instructions", "")
            
            # Create critique prompt
            critique_prompt = f"Please critique the document at {document_path}. {instructions}"
            
            # Create state for the subagent
            critique_state = {
                "messages": [{"role": "user", "content": critique_prompt}]
            }
            
            # Invoke the agent
            result = self.agent.invoke(critique_state)
            
            # Extract results
            critique_results = result["messages"][-1].content if result.get("messages") else ""
            
            # Emit critique completed event
            completion_event = Event(
                event_type=EventType.CRITIQUE_COMPLETED,
                data={
                    **event.data,
                    "critique_results": critique_results
                }
            )
            await self.emit_event_async(completion_event)
            
        except Exception as e:
            print(f"Error in critique: {e}")


class EventDrivenResearchOrchestrator(EventDrivenComponent):
    """Orchestrates event-driven research workflows."""
    
    def __init__(self, event_bus=None):
        super().__init__(event_bus or get_event_bus(), "research_orchestrator")
        self._research_context = {}
        self._pending_critiques = {}
        
    def _setup_event_handlers(self):
        """Setup event handlers for research orchestration."""
        self.event_bus.subscribe(EventType.ALL_TASKS_COMPLETED, self._handle_all_tasks_completed)
        self.event_bus.subscribe(EventType.RESEARCH_COMPLETED, self._handle_research_completed)
        self.event_bus.subscribe(EventType.CRITIQUE_COMPLETED, self._handle_critique_completed)
        self.event_bus.subscribe(EventType.FILE_CREATED, self._handle_file_created)
        
    def _handle_all_tasks_completed(self, event: Event):
        """Handle completion of all parallel tasks."""
        task_group = event.data.get("task_group", "default")
        
        if task_group == "research":
            # All research tasks completed, could trigger report generation
            self._trigger_report_generation(event)
        elif task_group == "critique":
            # All critique tasks completed, could trigger revisions
            self._trigger_revisions(event)
            
    def _handle_research_completed(self, event: Event):
        """Handle individual research completion."""
        if isinstance(event, ResearchEvent):
            task_group = event.data.get("task_group", "default")
            
            # Store research results
            if task_group not in self._research_context:
                self._research_context[task_group] = []
            
            self._research_context[task_group].append({
                "query": event.query,
                "agent": event.agent_name,
                "results": event.results,
                "timestamp": event.timestamp.isoformat()
            })
            
    def _handle_critique_completed(self, event: Event):
        """Handle critique completion."""
        task_id = event.data.get("task_id")
        if task_id in self._pending_critiques:
            self._pending_critiques[task_id]["status"] = "completed"
            self._pending_critiques[task_id]["results"] = event.data.get("critique_results", "")
            
    def _handle_file_created(self, event: Event):
        """Handle file creation events."""
        if isinstance(event, FileEvent) and event.file_path.endswith(".md"):
            # New report created, could trigger automatic critique
            self._maybe_trigger_critique(event)
            
    def _trigger_report_generation(self, event: Event):
        """Trigger report generation based on completed research."""
        # This could emit events to start report writing
        report_event = Event(
            event_type=EventType.PARALLEL_TASK_STARTED,
            data={
                "task_id": str(uuid4()),
                "task_group": "report_generation",
                "action": "generate_report",
                "research_context": self._research_context
            }
        )
        self.emit_event(report_event)
        
    def _trigger_revisions(self, event: Event):
        """Trigger revisions based on completed critiques."""
        # This could emit events to start revision tasks
        revision_event = Event(
            event_type=EventType.PARALLEL_TASK_STARTED,
            data={
                "task_id": str(uuid4()),
                "task_group": "revisions",
                "action": "revise_document",
                "critique_results": self._pending_critiques
            }
        )
        self.emit_event(revision_event)
        
    def _maybe_trigger_critique(self, file_event):
        """Maybe trigger automatic critique for new reports."""
        if "final_report" in file_event.file_path.lower():
            critique_event = Event(
                event_type=EventType.CRITIQUE_REQUESTED,
                data={
                    "task_id": str(uuid4()),
                    "task_group": "auto_critique",
                    "document_path": file_event.file_path,
                    "instructions": "Provide comprehensive critique of this research report"
                }
            )
            self.emit_event(critique_event)


def _create_event_driven_task_tool(tools, instructions, subagents: List[SubAgent], model, state_schema):
    """Create an event-driven version of the task tool."""
    
    # Create regular agents for backward compatibility
    agents = {
        "general-purpose": create_react_agent(model, prompt=instructions, tools=tools)
    }
    
    # Create event-driven subagents
    event_driven_agents = {}
    event_bus = get_event_bus()
    
    tools_by_name = {}
    for tool_ in tools:
        if not isinstance(tool_, BaseTool):
            tool_ = tool(tool_)
        tools_by_name[tool_.name] = tool_
        
    for _agent in subagents:
        # Create regular agent
        if "tools" in _agent:
            _tools = [tools_by_name[t] for t in _agent["tools"]]
        else:
            _tools = tools
        agents[_agent["name"]] = create_react_agent(
            model, prompt=_agent["prompt"], tools=_tools, state_schema=state_schema
        )
        
        # Create event-driven version
        event_driven_agents[_agent["name"]] = EventDrivenSubAgent(
            _agent, _tools, model, state_schema, event_bus
        )

    other_agents_string = [
        f"- {_agent['name']}: {_agent['description']}" for _agent in subagents
    ]

    @tool(
        description=TASK_DESCRIPTION_PREFIX.format(other_agents=other_agents_string)
        + TASK_DESCRIPTION_SUFFIX
        + "\n\nFor event-driven mode, use 'event-driven:' prefix in description to enable parallel processing."
    )
    def task(
        description: str,
        subagent_type: str,
        state: Annotated[DeepAgentState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        # Check if event-driven mode is requested
        event_driven_mode = description.startswith("event-driven:") or state.get("event_driven_mode", False)
        
        if event_driven_mode:
            # Handle event-driven task
            if description.startswith("event-driven:"):
                description = description[13:].strip()  # Remove prefix
                
            if subagent_type not in event_driven_agents:
                return f"Error: event-driven agent of type {subagent_type} not found. Available: {list(event_driven_agents.keys())}"
                
            # Emit research request event for event-driven processing
            task_id = str(uuid4())
            event_bus = get_event_bus()
            
            research_event = ResearchEvent(
                event_type=EventType.RESEARCH_REQUESTED,
                query=description,
                agent_name=subagent_type,
                data={
                    "task_id": task_id,
                    "task_group": "async_research",
                    "tool_call_id": tool_call_id
                }
            )
            event_bus.emit(research_event)
            
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            f"Started event-driven task '{description}' with agent '{subagent_type}' (Task ID: {task_id})",
                            tool_call_id=tool_call_id
                        )
                    ]
                }
            )
        else:
            # Use regular synchronous processing
            if subagent_type not in agents:
                return f"Error: invoked agent of type {subagent_type}, the only allowed types are {[f'`{k}`' for k in agents]}"
            
            sub_agent = agents[subagent_type]
            state["messages"] = [{"role": "user", "content": description}]
            result = sub_agent.invoke(state)
            
            return Command(
                update={
                    "files": result.get("files", {}),
                    "messages": [
                        ToolMessage(
                            result["messages"][-1].content, tool_call_id=tool_call_id
                        )
                    ],
                }
            )

    return task