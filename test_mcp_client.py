import asyncio
import sys
import os

# 将当前目录添加到 sys.path 以便导入 agent_tools
sys.path.append(os.getcwd())

from agent_tools.mcp.transport import StdioTransport
from agent_tools.mcp.client import McpClient

async def main():
    print("=== Testing MCP Client with Mock Server ===")
    
    # 1. Initialize Transport
    # Run the mock server script
    transport = StdioTransport("python", ["e:\\github\\ownAgent\\test_mcp_server.py"])
    
    # 2. Initialize Client
    client = McpClient(transport)
    
    try:
        # 3. Connect
        print("Connecting...")
        await client.connect()
        print("Connected!")
        
        # 4. List Tools
        print("\nListing Tools:")
        tools = await client.list_tools()
        for tool in tools:
            print(f" - {tool.name}: {tool.description}")
            
        # 5. Call Tool: mock_echo
        print("\nCalling mock_echo...")
        result = await client.call_tool("mock_echo", {"message": "Hello MCP!"})
        print(f"Result: {result}")
        
        # 6. Call Tool: mock_add
        print("\nCalling mock_add...")
        result = await client.call_tool("mock_add", {"a": 10, "b": 25})
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()
        print("\nClient closed.")

if __name__ == "__main__":
    asyncio.run(main())
