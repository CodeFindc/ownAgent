import sys
import os
import json

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from ag import ToolExecutor
from agent_tools.io import list_files, ListFilesArgs

executor = ToolExecutor()
executor.register(list_files, ListFilesArgs)

definitions = executor.get_definitions()
# Check list_files schema
tool_def = next((d for d in definitions if d['function']['name'] == 'list_files'), None)

if tool_def:
    print(f"Tool: {tool_def['function']['name']}")
    print(f"Description: {tool_def['function']['description'][:50]}...")
    print("Parameters:")
    print(json.dumps(tool_def['function']['parameters'], indent=2))
else:
    print("Tool list_files not found.")
