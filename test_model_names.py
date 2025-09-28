#!/usr/bin/env python3

import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini
api_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=api_key)

# Test different model names that should work with the SDK
model_names = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest", 
    "gemini-2.0-flash-exp",
    "models/gemini-1.5-flash"
]

print("🧪 Testing model names with Google AI SDK:\n")

for model_name in model_names:
    try:
        print(f"Testing: {model_name}")
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"temperature": 0.4}
        )
        
        response = model.generate_content("Say 'OK' if this works")
        if response.text:
            print(f"✅ SUCCESS: {model_name} works!")
            print(f"   Response: {response.text.strip()}\n")
            break
        else:
            print(f"❌ No response from {model_name}\n")
            
    except Exception as e:
        print(f"❌ ERROR with {model_name}: {e}\n")

else:
    print("❌ None of the model names worked!")
    print("💡 You may need to enable billing or wait for quota reset")