#!/usr/bin/env python3
"""
Test script for the Parallel Research Agent System

This script demonstrates the SMS Deep Researcher Agent Interaction Flow
with hierarchical research coordination and parallel sub-agent deployment.
"""

import os
import sys
from parallel_research_agent import parallel_research_agent

def test_parallel_research():
    """Test the parallel research agent with a sample query"""

    # Ensure required environment variable is set
    if "TAVILY_API_KEY" not in os.environ:
        print("Error: TAVILY_API_KEY environment variable must be set")
        print("Please set your Tavily API key: export TAVILY_API_KEY='your_key_here'")
        sys.exit(1)

    # Sample research query to test the system
    test_query = """
    I need a comprehensive analysis of artificial intelligence in healthcare.
    Please research the technical implementation challenges, market opportunities,
    academic research developments, regulatory landscape, and social implications
    of AI adoption in medical settings.
    """

    print("🔬 Testing Parallel Research Agent System")
    print("=" * 60)
    print(f"Research Query: {test_query.strip()}")
    print("=" * 60)
    print()

    print("🚀 Launching Lead Research Coordinator...")
    print("📋 Expected process:")
    print("  1. Research context initialization")
    print("  2. Strategy development")
    print("  3. Parallel sub-agent deployment:")
    print("     - Technical Researcher")
    print("     - Market Researcher")
    print("     - Academic Researcher")
    print("     - Regulatory Researcher")
    print("     - Social Impact Researcher")
    print("  4. Result synthesis")
    print("  5. Final comprehensive report")
    print()

    try:
        # Initialize agent state
        initial_state = {
            "messages": [{"role": "user", "content": test_query}],
            "files": {}
        }

        # Run the parallel research agent
        result = parallel_research_agent.invoke(initial_state)

        print("✅ Research completed successfully!")
        print("=" * 60)
        print("📊 Final Research Report:")
        print("=" * 60)
        print(result["messages"][-1].content)

        # Show file outputs if any were created
        if result.get("files"):
            print("\n📁 Research Files Created:")
            print("-" * 30)
            for filename, content in result["files"].items():
                print(f"📄 {filename}")
                print(f"   Size: {len(content)} characters")

    except Exception as e:
        print(f"❌ Error during research: {str(e)}")
        print("This might be due to:")
        print("- Missing TAVILY_API_KEY")
        print("- Network connectivity issues")
        print("- API rate limits")
        return False

    return True

if __name__ == "__main__":
    success = test_parallel_research()
    if success:
        print("\n🎉 Parallel Research Agent test completed successfully!")
    else:
        print("\n💥 Test failed - check error messages above")
        sys.exit(1)