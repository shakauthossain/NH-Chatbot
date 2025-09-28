#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import sys

# Add current directory to path so we can import our modules
sys.path.append('.')

# Load environment variables
load_dotenv()

try:
    from chatbot_prompt import detect_services_intent
    
    # Test various service inquiry messages
    test_messages = [
        "What services do you offer?",
        "Tell me about your services",
        "What do you do?",
        "What can you help me with?",
        "What are your capabilities?",
        "List your services",
        "What services are available?",
        "What kind of services do you provide?",
        "Hi there",  # Should be False
        "How much does it cost?",  # Should be False
        "I want to schedule a meeting",  # Should be False
        "What do you offer?",
        "What are your service offerings?",
        "Tell me what you can do for me"
    ]

    print("🔍 Testing services intent detection:\n")
    
    for message in test_messages:
        try:
            result = detect_services_intent(message)
            status = "✅" if result else "❌"
            print(f"{status} '{message}' -> Services Intent: {result}")
        except Exception as e:
            print(f"❌ Error testing '{message}': {e}")

    print(f"\n💡 Service inquiries should return True, others should return False!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project directory")
except Exception as e:
    print(f"❌ Error: {e}")