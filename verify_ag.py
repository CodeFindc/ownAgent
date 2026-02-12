import sys
import os
# Add the current directory to sys.path so we can import ag
sys.path.append(os.getcwd())
try:
    from ag import ToolExecutor, list_files, execute_command
    
    print("Successfully imported ag.")
    
    executor = ToolExecutor()
    
    # Register tools as done in ag.py
    from agent_tools.io import ListFilesArgs
    from agent_tools.system import ExecuteCommandArgs
    
    executor.register(list_files, ListFilesArgs)
    executor.register(execute_command, ExecuteCommandArgs)
    
    print("Successfully registered tools.")
    
    definitions = executor.get_definitions()
    tool_names = [d['function']['name'] for d in definitions]
    
    print(f"Registered tools: {tool_names}")
    
    if 'list_files' in tool_names and 'execute_command' in tool_names:
        print("Verification SUCCESS: Expected tools are present.")
    else:
        print("Verification FAILED: Missing expected tools.")
        
except ImportError as e:
    print(f"Verification FAILED: ImportError - {e}")
except Exception as e:
    print(f"Verification FAILED: {e}")
