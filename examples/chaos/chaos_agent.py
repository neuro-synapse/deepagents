import os
import subprocess
from deepagents import create_deep_agent

# Single AWS CLI tool - following the exact pattern from research_agent.py
def aws_cli(
    command: str,
    region: str = "us-east-1",
):
    """Execute AWS CLI commands for chaos engineering operations.
    
    Can be used for discovery, monitoring, chaos actions, and rollback.
    Examples:
    - Discovery: 'ec2 describe-instances --filters Name=tag:Environment,Values=staging'
    - Monitoring: 'logs get-log-events --log-group-name /aws/lambda/checkout'
    - Chaos: 'ec2 stop-instances --instance-ids i-1234567890abcdef0'
    - Rollback: 'ec2 start-instances --instance-ids i-1234567890abcdef0'
    """
    try:
        full_command = f"aws {command} --region {region} --output json"
        result = subprocess.run(
            full_command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            return f"Command succeeded:\n{result.stdout}"
        else:
            return f"Command failed (exit code {result.returncode}):\n{result.stderr}"
            
    except subprocess.TimeoutExpired:
        return "Command timed out after 5 minutes"
    except Exception as e:
        return f"Error executing command: {str(e)}"

# Sub-agent prompts - following research_agent.py pattern
designer_prompt = """You are a chaos engineering experiment designer. Your job is to design safe AWS-based chaos experiments.

Use the aws_cli tool to discover infrastructure and design experiments. Write your experiment plan to `experiment_plan.md`.

Only your FINAL answer will be passed on to the user. They will have NO knowledge of anything except your final message, so ensure your experiment plan is comprehensive!"""

safety_prompt = """You are a chaos engineering safety specialist. Your job is to ensure experiments are safe.

Use the aws_cli tool to verify safety. Write safety documentation to `safety_checklist.md`.

Only your FINAL answer will be passed on to the user. They will have NO knowledge of anything except your final message, so ensure your safety assessment is thorough!"""

executor_prompt = """You are a chaos engineering execution specialist. Your job is to safely execute experiments.

Use the aws_cli tool to execute experiments step by step. Log everything to `execution_log.md`.

Only your FINAL answer will be passed on to the user. They will have NO knowledge of anything except your final message, so ensure your execution log is detailed!"""

analyzer_prompt = """You are a chaos engineering analysis specialist. Your job is to analyze experiment results.

Use the aws_cli tool to collect data and analyze results. Write findings to `findings_report.md`.

Only your FINAL answer will be passed on to the user. They will have NO knowledge of anything except your final message, so ensure your analysis is comprehensive!"""

# Sub-agent definitions - following exact research_agent.py pattern
designer_sub_agent = {
    "name": "designer",
    "description": "Design chaos experiments using AWS services. Use when you need to plan what to test and how.",
    "prompt": designer_prompt,
    "tools": ["aws_cli"]
}

safety_sub_agent = {
    "name": "safety-checker",
    "description": "Review experiments for safety and create rollback plans. Use before executing anything.",
    "prompt": safety_prompt,
    "tools": ["aws_cli"]
}

executor_sub_agent = {
    "name": "executor",
    "description": "Execute chaos experiments step by step with monitoring. Use to actually run the experiments.",
    "prompt": executor_prompt,
    "tools": ["aws_cli"]
}

analyzer_sub_agent = {
    "name": "analyzer",
    "description": "Analyze experiment results and generate insights. Use after experiments complete.",
    "prompt": analyzer_prompt,
    "tools": ["aws_cli"]
}

# Main instructions - following research_agent.py pattern
chaos_instructions = """You are an expert chaos engineering agent for AWS environments. Your job is to safely test system resilience using AWS CLI commands.

The first thing you should do is to write the original user objective to `objective.txt` so you have a record of it.

Use the designer to create experiment plans, the safety-checker to verify safety, the executor to run experiments, and the analyzer to generate insights.

When you think you have enough information to create a final report, write it to `final_chaos_report.md`

You can call sub-agents multiple times until you are satisfied with the result.

Only edit files one at a time (if you call this tool in parallel, there may be conflicts).

Here are instructions for the final report:

<report_instructions>
CRITICAL: Make sure the answer is written in the same language as the human messages!

Please create a detailed chaos engineering report that:
1. Is well-organized with proper headings (# for title, ## for sections, ### for subsections)
2. Includes specific AWS resources tested and methods used
3. Documents exact AWS CLI commands executed
4. Provides detailed findings and system behavior observations
5. Includes actionable recommendations for improving resilience
6. Has a "Summary" section at the end with key takeaways

Structure your report appropriately based on the chaos engineering objective:
- Overview of what was tested
- Experiment methodology and execution
- Findings and observations
- System resilience assessment
- Recommendations for improvement
- Next steps

Each section should be detailed and actionable. Include specific AWS CLI commands and evidence from your testing.

Format the report in clear markdown with proper structure.
</report_instructions>

You have access to the aws_cli tool for all AWS operations.
"""

# Create the agent - following exact research_agent.py pattern
agent = create_deep_agent(
    [aws_cli],
    chaos_instructions,
    subagents=[designer_sub_agent, safety_sub_agent, executor_sub_agent, analyzer_sub_agent],
).with_config({"recursion_limit": 1000})
