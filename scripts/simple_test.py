"""
Simple API Key Test
"""

import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

print("="*60)
print("A.R.E.S. API Key Test")
print("="*60)

# Test environment variables
print("\n1. Environment Variables:")
openai_key = os.getenv("OPENAI_API_KEY")
google_key = os.getenv("GOOGLE_API_KEY")

if openai_key:
    print(f"   ✓ OPENAI_API_KEY: {openai_key[:20]}...")
else:
    print("   ✗ OPENAI_API_KEY: NOT SET")

if google_key:
    print(f"   ✓ GOOGLE_API_KEY: {google_key[:20]}...")
else:
    print("   ✗ GOOGLE_API_KEY: NOT SET")

# Test OpenAI
print("\n2. Testing OpenAI...")
try:
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=openai_key
    )
    
    response = llm.invoke("Say hello in 5 words")
    print(f"   ✓ OpenAI works!")
    print(f"   Response: {response.content}")
    
except Exception as e:
    print(f"   ✗ OpenAI failed: {e}")

# Test Gemini
print("\n3. Testing Google Gemini 2.0 Flash Experimental...")
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",  # En yeni model!
        google_api_key=google_key,
        convert_system_message_to_human=True
    )
    
    response = llm.invoke("Say hello in 5 words")
    print(f"   ✓ Gemini works!")
    print(f"   Response: {response.content}")
    
except Exception as e:
    print(f"   ✗ Gemini failed: {e}")

print("\n" + "="*60)
print("Test Complete!")
print("="*60)
