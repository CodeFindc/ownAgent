"""
测试 Skills 功能
"""
from pathlib import Path
from agent_tools.skills_loader import SkillsLoader, SkillMetadata
from agent_tools.skills_manager import SkillsManager

# 测试 1: 测试 SkillsLoader
print("=" * 50)
print("Test 1: SkillsLoader")
print("=" * 50)

skills_root = Path(".skills")
loader = SkillsLoader(skills_root)

# 加载所有元信息
metadata_list = loader.load_all_metadata()
print(f"Loaded {len(metadata_list)} skills:")
for metadata in metadata_list:
    print(f"  - {metadata.name}: {metadata.description}")

# 测试 2: 测试 SkillsManager
print("\n" + "=" * 50)
print("Test 2: SkillsManager")
print("=" * 50)

manager = SkillsManager(skills_root)
manager.load_skills()

# 测试搜索
print("\nSearch for 'uint':")
results = manager.search_skills("uint", limit=3)
for i, metadata in enumerate(results, 1):
    print(f"  {i}. {metadata.name}: {metadata.description}")

# 测试 3: 获取技能内容
print("\n" + "=" * 50)
print("Test 3: Get Skill Content")
print("=" * 50)

content = manager.get_skill_content("add-uint-support")
if content:
    print(f"Content length: {len(content)} characters")
    print(f"First 200 chars: {content[:200]}...")
else:
    print("Failed to load skill content")

# 测试 4: 获取摘要
print("\n" + "=" * 50)
print("Test 4: Get Metadata Summary")
print("=" * 50)

summary = manager.get_metadata_summary()
print(summary)

print("\n" + "=" * 50)
print("All tests completed!")
print("=" * 50)
