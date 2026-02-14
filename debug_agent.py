
import sys
import io
import os

# Set UTF-8 for stdout/stderr to handle emoji/special chars on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import asyncio
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
import httpx

# Load environment variables
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")
model = os.getenv("OPENAI_MODEL", "Qwen/Qwen3-235B-A22B-Thinking-2507")

print(f"Testing connection to: {base_url}")
print(f"Model: {model}")
print(f"API Key: {api_key[:8]}...")

async def test_simple():
    print("\n--- Test 1: Simple Chat (No Tools) ---")
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, http_client=httpx.AsyncClient(verify=False))
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            temperature=0,
        )
        print("Success! Response:")
        print(response.choices[0].message.content)
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

async def test_with_tools():
    print("\n--- Test 2: Chat with Tools Schema ---")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "arg": {"type": "string"}
                    }
                }
            }
        }
    ]
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, http_client=httpx.AsyncClient(verify=False))
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Call the test tool with arg='hello'"}],
            tools=tools,
            tool_choice="auto",
            temperature=0,
        )
        print("Success! Response:")
        print(response.choices[0].message)
        return True
    except Exception as e:
        print(f"Failed with Tools: {e}")
        return False

async def main():
    success_simple = await test_simple()
    if success_simple:
        await test_with_tools()
    else:
        print("Skipping tools test because simple test failed.")

if __name__ == "__main__":
    asyncio.run(main())
