"""Event-driven research agent example.

This demonstrates how to use the event-driven capabilities of deepagents
for parallel research processing with automatic coordination.
"""

import os
from typing import Literal

from tavily import TavilyClient
from deepagents import create_deep_agent, SubAgent

# It's best practice to initialize the client once and reuse it.
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

# Search tool to use to do research
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search"""
    search_docs = tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )
    return search_docs


# Event-driven research sub-agent prompt
sub_research_prompt = """You are a dedicated researcher working in an event-driven environment. Your job is to conduct research based on user questions and emit appropriate events.

When you complete your research:
1. Conduct thorough research on the given topic
2. Provide a detailed answer with your findings
3. Your final answer will be automatically processed by the event system

You work as part of a parallel research system, so focus on your specific research task and provide comprehensive results.

Only your FINAL answer will be passed on to the coordination system, so make sure your final message contains all the important findings!"""

research_sub_agent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions in parallel. Can be called multiple times simultaneously for different aspects of a research topic. Each instance focuses on one specific research question.",
    "prompt": sub_research_prompt,
    "tools": ["internet_search"]
}

# Event-driven critique sub-agent prompt  
sub_critique_prompt = """You are a dedicated editor working in an event-driven system. You critique reports automatically when they are created.

You can find the report to critique in the agent's file system.
You can find the original question/topic for this report in `question.txt` if available.

Provide a detailed critique focusing on:
- Content completeness and accuracy
- Structure and organization  
- Writing quality and clarity
- Areas that need improvement
- Missing important information

You can use the search tool to verify information if needed.

Your critique will be automatically processed by the event system for potential revisions."""

critique_sub_agent = {
    "name": "critique-agent", 
    "description": "Used to automatically critique research reports. Provides comprehensive feedback on content, structure, and quality.",
    "prompt": sub_critique_prompt,
    "tools": ["internet_search"]
}

# Event-driven research instructions
research_instructions = """You are an expert researcher operating in an EVENT-DRIVEN mode. This means you can conduct multiple research tasks in parallel and coordinate them automatically.

IMPORTANT: You are now operating in event-driven mode, which enables powerful parallel processing capabilities:

## Event-Driven Research Workflow

1. **Record the Question**: First, write the original user question to `question.txt`

2. **Plan Parallel Research**: Break down complex research topics into multiple parallel research tasks using `start_parallel_research`

3. **Monitor Progress**: Use `get_event_status` to check the status of your parallel research tasks

4. **Generate Reports**: When research is complete, write your findings to `final_report.md` using `write_file_with_events`

5. **Request Critique**: Use `request_critique` to automatically get feedback on your reports

6. **Coordinate Revisions**: The event system will automatically coordinate revisions based on critique feedback

## Key Event-Driven Tools Available:

- `start_parallel_research(query, agent_name, task_group)`: Start research that runs in parallel
- `get_event_status(task_group, limit)`: Check status of active research tasks  
- `write_file_with_events(file_path, content)`: Write files with automatic event emission
- `request_critique(document_path, instructions)`: Request automatic critique
- `write_todos_with_events(todos)`: Update todos with event coordination

## Parallel Research Strategy:

Instead of calling research agents sequentially, use `start_parallel_research` to launch multiple research tasks simultaneously:

Example:
- `start_parallel_research("economic impact of topic", "research-agent", "main_research")`
- `start_parallel_research("social implications of topic", "research-agent", "main_research")` 
- `start_parallel_research("technical aspects of topic", "research-agent", "main_research")`

Then monitor with `get_event_status(task_group="main_research")` to see when all tasks complete.

## Report Generation:

Use `write_file_with_events` instead of regular `write_file` to enable automatic critique triggering:
- Writing to files ending in `.md` will automatically trigger critique requests
- The event system coordinates between research completion, report generation, and critique

## Language Requirements:

CRITICAL: Make sure the answer is written in the same language as the human messages! The report should be in the SAME language as the QUESTION, not the language/country that the question is ABOUT.

## Report Structure Guidelines:

Please create a detailed answer that:
1. Is well-organized with proper headings (# for title, ## for sections, ### for subsections)
2. Includes specific facts and insights from parallel research
3. References sources using [Title](URL) format
4. Provides balanced, comprehensive analysis using ALL parallel research results
5. Includes a "Sources" section with all referenced links

The event-driven system allows you to be more thorough and efficient by conducting research in parallel while maintaining coordination.

You have access to the same file system tools and can coordinate with critique agents automatically through events."""

# Create the event-driven agent
agent = create_deep_agent(
    [internet_search],
    research_instructions,
    subagents=[critique_sub_agent, research_sub_agent],
    event_driven=True  # Enable event-driven mode
).with_config({"recursion_limit": 1000})


# Example usage function
async def example_event_driven_research():
    """Example of how to use the event-driven research agent."""
    
    # Example research query
    query = "What are the key trends in artificial intelligence research for 2024?"
    
    result = agent.invoke({
        "messages": [{"role": "user", "content": query}],
        "event_driven_mode": True
    })
    
    print("Research completed!")
    print("Files created:", result.get("files", {}).keys())
    print("Events generated:", len(result.get("events", [])))
    print("Active tasks:", result.get("active_tasks", {}))
    
    return result


# Synchronous example for comparison
def example_traditional_research():
    """Example of traditional synchronous research for comparison."""
    
    # Create traditional agent for comparison
    traditional_agent = create_deep_agent(
        [internet_search],
        research_instructions.replace("EVENT-DRIVEN mode", "traditional mode"),
        subagents=[critique_sub_agent, research_sub_agent],
        event_driven=False  # Traditional synchronous mode
    ).with_config({"recursion_limit": 1000})
    
    query = "What are the key trends in artificial intelligence research for 2024?"
    
    result = traditional_agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    
    print("Traditional research completed!")
    print("Files created:", result.get("files", {}).keys())
    
    return result


if __name__ == "__main__":
    print("Event-driven research agent example")
    print("=" * 50)
    
    # Run traditional research
    print("\n1. Traditional Research (Sequential):")
    traditional_result = example_traditional_research()
    
    # Run event-driven research  
    print("\n2. Event-Driven Research (Parallel):")
    import asyncio
    event_driven_result = asyncio.run(example_event_driven_research())
    
    print("\nComparison:")
    print(f"Traditional - Files: {len(traditional_result.get('files', {}))}")
    print(f"Event-driven - Files: {len(event_driven_result.get('files', {}))}, Events: {len(event_driven_result.get('events', []))}")