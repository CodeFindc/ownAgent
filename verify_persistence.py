
import asyncio
from agent_tools.base import ToolContext
from agent_tools.interaction import update_todo_list, UpdateTodoListArgs

class MockRuntime:
    def __init__(self):
        self.tool_context = ToolContext(workspace_root=".", todos=["[ ] Task 1"])

    async def step(self):
        print(f"Step Start: {self.tool_context.todos}")
        
        # Simulate tool execution
        args = UpdateTodoListArgs(todos="[x] Task 1\n[ ] Task 2")
        print(f"Executing Update with: {args.todos}")
        update_todo_list(self.tool_context, args)
        
        print(f"Step End: {self.tool_context.todos}")

async def test_loop():
    runtime = MockRuntime()
    await runtime.step()
    
    # Check next step
    print("\n--- Next Step ---")
    await runtime.step()

if __name__ == "__main__":
    asyncio.run(test_loop())
