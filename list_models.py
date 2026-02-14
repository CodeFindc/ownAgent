
import os
import asyncio
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL")

async def list_models():
    print(f"Listing models from: {base_url}")
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=base_url, http_client=httpx.AsyncClient(verify=False))
        models = await client.models.list()
        for m in models.data:
            print(f"- {m.id}")
    except Exception as e:
        print(f"Failed to list models: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
