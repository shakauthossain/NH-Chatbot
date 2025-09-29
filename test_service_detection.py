#!/usr/bin/env python3

# Test script to verify the enhanced service detection system
import sys
sys.path.append('.')

from chatbot_prompt import detect_specific_service_inquiry, detect_services_intent

def test_enhanced_service_detection():
    print("Testing Enhanced Service Detection System...")
    print("="*60)
    
    # Test cases for specific service inquiries
    specific_service_tests = [
        "Tell me about web development",
        "What do you offer for app development?", 
        "I need UI design services",
        "Do you do digital marketing?",
        "What about SEO services?",
        "I'm interested in branding",
        "Tell me about video production",
        "What is resource augmentation?"
    ]
    
    print("SPECIFIC SERVICE INQUIRIES:")
    print("-" * 40)
    for query in specific_service_tests:
        is_specific, enhanced_query, service_name = detect_specific_service_inquiry(query)
        print(f"Query: '{query}'")
        print(f"  Specific: {is_specific}")
        if is_specific:
            print(f"  Service: {service_name}")
            print(f"  Enhanced: {enhanced_query}")
        print()
    
    # Test cases for general service inquiries (should show list)
    general_service_tests = [
        "What services do you offer?",
        "Tell me about your services",
        "What do you do?",
        "List your services"
    ]
    
    print("GENERAL SERVICE INQUIRIES (Should show list):")
    print("-" * 50)
    for query in general_service_tests:
        is_general = detect_services_intent(query)
        is_specific, _, _ = detect_specific_service_inquiry(query)
        print(f"Query: '{query}'")
        print(f"  General services: {is_general}")
        print(f"  Specific service: {is_specific}")
        print()

if __name__ == "__main__":
    test_enhanced_service_detection()