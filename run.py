#!/usr/bin/env python3
"""
Open Deep Research Runner

A flexible script to run deep research analysis on any GitHub repository
with any query using the design doc agent.

Usage:
    python run.py "Your research query" "https://github.com/owner/repo"
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from dotenv import load_dotenv
from open_deep_research.deep_researcher import design_doc_agent

# Load environment variables
load_dotenv()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Run deep research analysis on any GitHub repository",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py "Design a usage-based pricing model" "https://github.com/entelligenceAI/backend"
  python run.py "Analyze the authentication system" "https://github.com/owner/repo"
  python run.py "How does the payment processing work?" "https://github.com/company/api"
        """
    )
    
    parser.add_argument(
        "query",
        help="The research query or question to analyze"
    )
    
    parser.add_argument(
        "repo_url",
        help="GitHub repository URL (e.g., https://github.com/owner/repo)"
    )
    
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model to use (default: gpt-4.1-mini)"
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Temperature for the model (default: 0.1)"
    )
    
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=1,
        help="Maximum analysis iterations (default: 1)"
    )
    
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=1,
        help="Maximum concurrent analysis units (default: 1)"
    )
    
    parser.add_argument(
        "--output",
        help="Output filename (default: auto-generated based on repo and timestamp)"
    )
    
    return parser.parse_args()

def generate_output_filename(repo_url: str, query: str) -> str:
    """Generate a filename based on repo and query"""
    # Extract repo name from URL
    repo_name = repo_url.rstrip('/').split('/')[-1]
    owner = repo_url.rstrip('/').split('/')[-2]
    
    # Clean query for filename
    query_clean = "".join(c for c in query.lower() if c.isalnum() or c in (' ', '-', '_')).strip()
    query_clean = query_clean.replace(' ', '_')[:50]  # Limit length
    
    # Add timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return f"{owner}_{repo_name}_{query_clean}_{timestamp}.md"

async def interactive_clarification_loop(args, config, filename, previous_content):
    """
    Interactive loop for clarifications and regeneration
    """
    print("\n" + "=" * 70)
    print("Interactive Clarification Mode")
    print("=" * 70)
    print("Now you can ask for clarifications, changes, or additional analysis!")
    print("Type your follow-up question or request, or 'quit' to exit.")
    print()
    
    iteration = 1
    current_content = previous_content
    
    while True:
        try:
            # Get user input
            user_input = input("Your clarification/change request (or 'quit' to exit): ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Exiting clarification mode. Final analysis saved!")
                break
            
            if not user_input:
                print("Please enter a clarification request or 'quit' to exit.")
                continue
            
            print(f"\nProcessing clarification #{iteration}...")
            print(f"Request: {user_input}")
            print("Regenerating analysis...")
            print()
            
            # Create a follow-up query that includes the previous analysis and new request
            follow_up_query = f"""
Based on the previous analysis, please address this follow-up request:

{user_input}

Previous analysis context:
{current_content[:2000]}...

Please provide an updated analysis that addresses the new request while maintaining relevant context from the previous analysis.
"""
            
            # Run the analysis again with the follow-up query
            result = await design_doc_agent.ainvoke(
                {"messages": [{"role": "user", "content": follow_up_query}]},
                config=config
            )
            
            # Extract the new content
            final_message = result["messages"][-1]
            if hasattr(final_message, 'content'):
                new_content = final_message.content
            elif isinstance(final_message, dict) and 'content' in final_message:
                new_content = final_message['content']
            else:
                new_content = str(final_message)
            
            current_content = new_content
            
            print("Updated Analysis Generated!")
            print("=" * 50)
            
            # Generate new filename for the updated version
            base_filename = filename.rsplit('.', 1)[0]  # Remove .md extension
            updated_filename = f"{base_filename}_v{iteration + 1}.md"
            
            # Save the updated analysis
            with open(updated_filename, "w") as f:
                f.write(f"# Deep Research Analysis (Updated)\n")
                f.write(f"*Generated by Entelligence Deep Research*\n\n")
                f.write(f"**Repository:** {args.repo_url}\n")
                f.write(f"**Original Query:** {args.query}\n")
                f.write(f"**Clarification #{iteration}:** {user_input}\n")
                f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"**Model:** {args.model}\n\n")
                f.write("---\n\n")
                f.write(new_content)
            
            print(f"Updated analysis saved to: {updated_filename}")
            
            # Ask if they want to continue
            print(f"\nAnalysis updated! You can ask for more clarifications or type 'quit' to finish.")
            
            iteration += 1
            
        except KeyboardInterrupt:
            print("\n\nExiting clarification mode...")
            break
        except Exception as e:
            print(f"Error during clarification: {e}")
            print("Please try again or type 'quit' to exit.")

async def run_deep_research(args):
    """
    Run deep research analysis with the provided parameters
    """
    print("Open Deep Research Runner")
    print("=" * 70)
    print(f"Query: {args.query}")
    print(f"Repository: {args.repo_url}")
    print(f"Model: {args.model}")
    print()
    
    # Check for required environment variables
    github_token = os.getenv("GITHUB_ACCESS_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not github_token or not openai_key:
        print("Missing required environment variables:")
        if not github_token:
            print("   - GITHUB_ACCESS_TOKEN")
        if not openai_key:
            print("   - OPENAI_API_KEY")
        print("\nPlease set these environment variables or add them to a .env file")
        return

    # Configuration for analysis
    config = {
        "configurable": {
            "allow_clarification": False,
            "max_concurrent_analysis_units": args.max_concurrent,
            "max_analysis_iterations": args.max_iterations,
            "github_repo_url": args.repo_url,
            "github_access_token": github_token,
            "model": args.model,
            "temperature": args.temperature,
        }
    }

    try:
        print("Analyzing repository...")
        print("Processing your query...")
        print("This analysis may take several minutes depending on repository size...")
        print()
        
        # Run the design doc agent
        result = await design_doc_agent.ainvoke(
            {"messages": [{"role": "user", "content": args.query}]},
            config=config
        )
        
        print("Analysis Complete!")
        print("=" * 60)
        
        # Extract the content
        final_message = result["messages"][-1]
        if hasattr(final_message, 'content'):
            content = final_message.content
        elif isinstance(final_message, dict) and 'content' in final_message:
            content = final_message['content']
        else:
            content = str(final_message)
        
        # Generate filename if not provided
        if args.output:
            filename = args.output
        else:
            filename = generate_output_filename(args.repo_url, args.query)
        
        # Save the analysis document
        with open(filename, "w") as f:
            f.write(f"# Deep Research Analysis\n")
            f.write(f"*Generated by Open Deep Research*\n\n")
            f.write(f"**Repository:** {args.repo_url}\n")
            f.write(f"**Query:** {args.query}\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Model:** {args.model}\n\n")
            f.write("---\n\n")
            f.write(content)

        print(f"Analysis saved to: {filename}")

        await interactive_clarification_loop(args, config, filename, content)
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Validate GitHub URL
    if not args.repo_url.startswith("https://github.com/"):
        print("Error: Repository URL must be a valid GitHub URL starting with https://github.com/")
        sys.exit(1)
    
    # Run the analysis
    asyncio.run(run_deep_research(args))

if __name__ == "__main__":
    main() 