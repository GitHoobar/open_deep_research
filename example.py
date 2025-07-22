#!/usr/bin/env python3
"""
Design Doc Agent Test: Usage-Based Pricing Model for Code Review & Doc Generation

This script will analyze the entelligenceAI/backend repository and generate a comprehensive 
design document for implementing a usage-based pricing model with credits.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from dotenv import load_dotenv
from open_deep_research.deep_researcher import design_doc_agent

# Load environment variables
load_dotenv()

async def generate_pricing_model_design():
    """
    Generate a design document for usage-based pricing model
    """
    print("🏗️  Design Doc Agent - Usage-Based Pricing Model")
    print("=" * 70)
    print("🔒 Repository: entelligenceAI/backend")
    print("💰 Focus: Usage-Based Pricing with Credits System")
    print()
    
    # Check for required environment variables
    github_token = os.getenv("GITHUB_ACCESS_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not github_token or not openai_key:
        print("❌ Missing required environment variables:")
        if not github_token:
            print("   - GITHUB_ACCESS_TOKEN")
        if not openai_key:
            print("   - OPENAI_API_KEY")
        return

    # Detailed query for pricing model design
    pricing_query = """
    I need to build a comprehensive usage-based pricing model for a code review and documentation generation platform. Please analyze the current backend architecture and provide a detailed design document that covers:

    ## Core Requirements:
    1. **Credits System Architecture**
       - Users receive initial credits upon signup/subscription
       - Credits are consumed based on usage (code review, doc generation)
       - Credit balance tracking and management
       - Credit expiration and renewal policies

    2. **Usage Tracking & Metering**
       - Track code review API calls and complexity
       - Monitor documentation generation requests and output length
       - Real-time usage monitoring and analytics
       - Rate limiting based on credit availability

    3. **Pricing Tiers & Models**
       - Free tier with limited credits
       - Multiple paid tiers with different credit allocations
       - Pay-as-you-go option for additional credits
       - Enterprise/team pricing models

    4. **Billing & Payment Integration**
       - Subscription management (monthly/yearly)
       - Credit top-up purchasing
       - Payment processing integration (Stripe/PayPal)
       - Invoice generation and billing history

    5. **Credit Consumption Logic**
       - Define credit costs for different operations:
         * Simple code review: X credits
         * Complex code review: Y credits  
         * Documentation generation: Z credits per page/word
       - Dynamic pricing based on complexity/size
       - Bulk operation discounts

    6. **User Experience & Notifications**
       - Credit balance dashboard
       - Usage analytics and reporting
       - Low credit warnings and notifications
       - Upgrade prompts and recommendations

    7. **Admin & Analytics**
       - Revenue tracking and reporting
       - User behavior analytics
       - Credit usage patterns
       - Pricing optimization insights

    ## Technical Implementation:
    - Database schema for credits, subscriptions, usage tracking
    - API endpoints for credit management
    - Background jobs for billing and notifications
    - Integration with existing authentication system
    - Scalable architecture for high-volume usage tracking

    ## Business Considerations:
    - Competitive pricing analysis
    - Customer acquisition and retention strategies
    - Revenue optimization and forecasting
    - Compliance with payment regulations

    Please analyze the current backend codebase and provide a comprehensive design that integrates seamlessly with the existing architecture while implementing this usage-based pricing model with credits.
    """

    # Configuration for comprehensive analysis
    config = {
        "configurable": {
            "allow_clarification": False,
            "max_concurrent_analysis_units": 8,  # Enhanced parallel analysis
            "max_analysis_iterations": 15,  # Deep analysis for complex pricing system
            "github_repo_url": "https://github.com/Entelligence-AI/backend",
            "github_access_token": github_token,
            "model": "gpt-4o",  # Best model for complex business logic
            "temperature": 0.1,  # Focused, precise responses
        }
    }

    try:
        print("🔍 Analyzing repository architecture...")
        print("💰 Designing usage-based pricing model...")
        print("⏳ This comprehensive analysis may take 3-5 minutes...")
        print()
        
        # Run the design doc agent
        result = await design_doc_agent.ainvoke(
            {"messages": [{"role": "user", "content": pricing_query}]},
            config=config
        )
        
        print("✅ Pricing Model Design Document Generated!")
        print("=" * 60)
        
        # Extract the content
        final_message = result["messages"][-1]
        if hasattr(final_message, 'content'):
            content = final_message.content
        elif isinstance(final_message, dict) and 'content' in final_message:
            content = final_message['content']
        else:
            content = str(final_message)
        
        # Display preview
        print("📄 Design Document Preview:")
        print("-" * 40)
        preview_length = 1000
        print(content[:preview_length] + "..." if len(content) > preview_length else content)
        
        # Save the comprehensive design document
        filename = "entelligence_usage_based_pricing_model_design_2.md"
        with open(filename, "w") as f:
            f.write("# Usage-Based Pricing Model Design - entelligenceAI/backend\n")
            f.write("*Generated by Entelligence Doc Agent*\n\n")
            f.write(content)

            print(f" Done!")
        
    except Exception as e:
        print(f" Error during analysis: {e}")
if __name__ == "__main__":
    print()
    
    asyncio.run(generate_pricing_model_design()) 