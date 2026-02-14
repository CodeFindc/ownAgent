
import asyncio
from agent_tools.base import ToolContext
from agent_tools.interaction import update_todo_list, UpdateTodoListArgs

async def test_persistence():
    # Setup Context
    ctx = ToolContext(workspace_root=".", todos=["[ ] Task 1"])
    print(f"Initial: {ctx.todos}")
    
    # Update Context via Tool
    args = UpdateTodoListArgs(todos="[x] Task 1\n[ ] Task 2")
    update_todo_list(ctx, args)
    
    print(f"After Update: {ctx.todos}")
    
    if ctx.todos == ["[x] Task 1", "[ ] Task 2"]:
        print("SUCCESS: Context updated and persisted.")
    else:
        print("FAILED: Context did not update.")

if __name__ == "__main__":
    asyncio.run(test_persistence())
