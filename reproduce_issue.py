import os
import sys
from pathlib import Path
sys.path.append(r"d:\iso\tmp\tools")

from agent_tools.diff import apply_diff, ApplyDiffArgs
from agent_tools.base import ToolContext

# Setup
file_path = Path("test_target.txt")
file_path.write_text('line1\nline2\nline3\n', encoding='utf-8')

# Diff without newline at the end of replacement
# Case: Replacing 'line2' with 'new_line2' but forgetting newline
diff_content = """<<<<<<< SEARCH
:start_line:2
-------
line2
=======
new_line2
>>>>>>> REPLACE"""

# Simulate context
class MockContext:
    workspace_root = Path(os.getcwd())

ctx = MockContext()
args = ApplyDiffArgs(path="test_target.txt", diff=diff_content)

print(f"Applying diff to {file_path.absolute()}")
result = apply_diff(ctx, args)
print(f"Result: {result.success}, {result.output}")

# Check content
content = file_path.read_text(encoding='utf-8')
print("--- File Content ---")
print(content)
print("--------------------")

expected = "line1\nnew_line2\nline3\n"
if content == "line1\nnew_line2line3\n":
    print("REPRODUCED: Lines merged incorrectly.")
elif content == expected:
    print("NOT REPRODUCED: Lines handled correctly.")
else:
    print(f"OTHER RESULT: {content!r}")
