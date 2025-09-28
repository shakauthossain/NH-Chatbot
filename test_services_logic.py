#!/usr/bin/env python3

# Simple test of services detection logic (without AI part)
def test_services_keywords_only(user_input: str) -> bool:
    """Test only the keyword matching part of services detection"""
    service_keywords = [
        "services", "what do you do", "what do you offer", "what services",
        "service list", "what can you help", "capabilities", "offerings",
        "what do you provide", "what are your services", "list your services",
        "tell me about your services", "services you offer", "what kind of services",
        "services available", "service offerings", "what services do you have"
    ]
    
    input_lower = user_input.lower().strip()
    
    # Direct keyword match
    return any(keyword in input_lower for keyword in service_keywords)

# Test various service inquiry messages
test_messages = [
    ("What services do you offer?", True),
    ("Tell me about your services", True),
    ("What do you do?", True),
    ("What can you help me with?", True),
    ("What are your capabilities?", True),
    ("List your services", True),
    ("What services are available?", True),
    ("What kind of services do you provide?", True),
    ("Hi there", False),
    ("How much does it cost?", False),
    ("I want to schedule a meeting", False),
    ("What do you offer?", True),
    ("What are your service offerings?", True),
    ("Tell me what you can do for me", False),  # This would need AI detection
    ("What services do you have?", True)
]

print("🔍 Testing services keyword detection:\n")

correct = 0
total = len(test_messages)

for message, expected in test_messages:
    result = test_services_keywords_only(message)
    status = "✅" if result == expected else "❌"
    if result == expected:
        correct += 1
    print(f"{status} '{message}' -> Expected: {expected}, Got: {result}")

print(f"\n📊 Accuracy: {correct}/{total} ({correct/total*100:.1f}%)")
print(f"💡 Keywords catch most service inquiries. AI will handle edge cases!")

# Test the services response format
services_response = """Here are our comprehensive services:

🌐 Web & App Development - Custom websites and mobile applications tailored to your needs

🎨 User Experience Design - Intuitive and engaging user interfaces that delight your customers

📊 Strategy & Digital Marketing - Data-driven marketing strategies to grow your business

🎥 Video Production & Photography - Professional visual content that tells your story

🏷️ Branding & Communication - Complete brand identity and messaging solutions

🔍 Search Engine Optimization - Get found online with our proven SEO strategies

👥 Resource Augmentation - Skilled professionals to extend your team capabilities

Ready to transform your digital presence? Let's discuss how we can help your business thrive!"""

print(f"\n📋 Sample Services Response:")
print(services_response)