"""
=============================================================================
ownAgent - 技能加载器模块
=============================================================================

本文件实现了技能系统的加载功能：

1. SkillsLoader - 技能加载器类
2. SkillMetadata - 技能元信息模型
3. Skill - 技能完整数据模型

功能说明：
- 从 .skills 目录加载技能文件
- 解析 Markdown 文件的 front matter（元信息）
- 支持按需加载完整内容
- 实现内容缓存提高性能

技能文件格式：
    ---
    name: 技能名称
    description: 技能描述
    tags: [标签1, 标签2]
    ---
    
    # 技能标题
    
    技能的详细内容...

目录结构：
    .skills/
    ├── create_api/
    │   └── SKILL.md
    ├── write_tests/
    │   └── SKILL.md
    └── ...

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import os               # 操作系统接口
import re               # 正则表达式，用于解析 front matter
from pathlib import Path  # 面向对象的文件路径处理
from typing import Optional, List  # 类型提示
from datetime import datetime  # 日期时间处理

# =============================================================================
# 第三方库导入
# =============================================================================

from pydantic import BaseModel, Field  # 数据验证和设置管理


# =============================================================================
# 数据模型定义
# =============================================================================

class SkillMetadata(BaseModel):
    """
    技能元信息模型（轻量级）。
    
    只包含技能的基本信息，不包含完整内容。
    用于快速检索和列表展示。
    
    属性:
        name (str): 技能名称
            - 唯一标识符
            - 用于引用和搜索
        
        description (str): 技能描述
            - 简短描述技能的功能
            - 用于搜索匹配和展示
        
        path (Path): 技能文件路径
            - 指向 SKILL.md 文件
            - 用于后续加载完整内容
    
    示例:
        >>> metadata = SkillMetadata(
        ...     name="create_api",
        ...     description="创建 REST API 端点",
        ...     path=Path(".skills/create_api/SKILL.md")
        ... )
    """
    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="技能描述")
    path: Path = Field(..., description="技能文件路径")


class Skill(BaseModel):
    """
    技能完整数据模型。
    
    包含技能的所有信息，包括完整内容。
    用于实际执行技能任务。
    
    属性:
        name (str): 技能名称
        description (str): 技能描述
        content (str): 技能完整内容
            - Markdown 格式
            - 包含详细指令和步骤
        path (Path): 技能文件路径
        loaded_at (datetime): 加载时间
            - 自动记录
            - 可用于缓存管理
    
    示例:
        >>> skill = Skill(
        ...     name="create_api",
        ...     description="创建 REST API 端点",
        ...     content="# 创建 API\\n\\n详细步骤...",
        ...     path=Path(".skills/create_api/SKILL.md")
        ... )
    """
    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="技能描述")
    content: str = Field(..., description="技能完整内容（markdown）")
    path: Path = Field(..., description="技能文件路径")
    loaded_at: datetime = Field(
        default_factory=datetime.now,  # 默认为当前时间
        description="加载时间"
    )


# =============================================================================
# 技能加载器类
# =============================================================================

class SkillsLoader:
    """
    技能加载器 - 从 .skills 目录加载技能。
    
    这个类负责：
    - 扫描技能目录
    - 解析技能文件的元信息
    - 按需加载完整内容
    - 管理内容缓存
    
    设计原则：
    - 元信息轻量加载：启动时只加载元信息
    - 内容按需加载：只有需要时才加载完整内容
    - 缓存优化：已加载的内容会被缓存
    
    属性:
        skills_root (Path): 技能根目录
        _content_cache (dict): 内容缓存字典
    
    使用示例:
        >>> loader = SkillsLoader(Path(".skills"))
        >>> metadata_list = loader.load_all_metadata()
        >>> content = loader.load_skill_content("create_api")
    """
    
    def __init__(self, skills_root: Path):
        """
        初始化技能加载器。
        
        参数:
            skills_root (Path): 技能根目录路径
                - 默认为 .skills
                - 每个子目录是一个技能
                - 每个技能目录下有 SKILL.md 文件
        """
        self.skills_root = Path(skills_root)
        # 内容缓存：技能名称 -> 内容
        self._content_cache: dict[str, str] = {}
        
    def load_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """
        加载单个技能的元信息。
        
        只加载 name 和 description，不加载完整内容。
        这是轻量级操作，适合启动时批量执行。
        
        参数:
            skill_name (str): 技能名称（目录名）
        
        返回:
            Optional[SkillMetadata]: 技能元信息，加载失败返回 None
        
        失败原因:
            - 技能文件不存在
            - front matter 格式错误
            - 缺少必要字段（name 或 description）
        
        示例:
            >>> metadata = loader.load_skill_metadata("create_api")
            >>> if metadata:
            ...     print(f"{metadata.name}: {metadata.description}")
        """
        # 构建技能文件路径
        skill_path = self.skills_root / skill_name / "SKILL.md"
        
        # 检查文件存在
        if not skill_path.exists():
            return None
            
        try:
            # 读取文件内容
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 front matter（YAML 格式的元数据）
            metadata = self._parse_front_matter(content)
            
            # 检查必要字段
            if not metadata.get('name') or not metadata.get('description'):
                return None
                
            # 创建并返回元信息对象
            return SkillMetadata(
                name=metadata['name'],
                description=metadata['description'],
                path=skill_path
            )
        except Exception as e:
            print(f"[WARNING] 加载技能元信息失败 {skill_name}: {e}")
            return None
    
    def load_all_metadata(self) -> List[SkillMetadata]:
        """
        加载所有技能的元信息。
        
        遍历技能目录，加载每个技能的元信息。
        不加载完整内容，适合启动时调用。
        
        返回:
            List[SkillMetadata]: 技能元信息列表
        
        流程:
            1. 检查技能目录是否存在
            2. 遍历所有子目录
            3. 对每个目录调用 load_skill_metadata
            4. 收集成功的元信息
        """
        metadata_list = []
        
        # 检查技能目录是否存在
        if not self.skills_root.exists():
            print(f"[INFO] 技能目录不存在: {self.skills_root}")
            return metadata_list
        
        # 遍历技能目录
        for skill_dir in self.skills_root.iterdir():
            # 跳过非目录文件
            if not skill_dir.is_dir():
                continue
                
            # 获取技能名称（目录名）
            skill_name = skill_dir.name
            
            # 加载元信息
            metadata = self.load_skill_metadata(skill_name)
            
            if metadata:
                metadata_list.append(metadata)
                print(f"[INFO] 加载技能元信息: {metadata.name}")
        
        return metadata_list
    
    def load_skill_content(self, skill_name: str) -> Optional[str]:
        """
        加载技能的完整内容。
        
        按需加载，只有当需要使用技能时才调用。
        加载后会缓存内容，避免重复读取文件。
        
        参数:
            skill_name (str): 技能名称
        
        返回:
            Optional[str]: 技能的完整 Markdown 内容，失败返回 None
        
        缓存策略:
            - 首次加载：读取文件并缓存
            - 后续加载：直接返回缓存内容
        """
        # 检查缓存
        if skill_name in self._content_cache:
            return self._content_cache[skill_name]
        
        # 构建文件路径
        skill_path = self.skills_root / skill_name / "SKILL.md"
        
        # 检查文件存在
        if not skill_path.exists():
            return None
            
        try:
            # 读取文件
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 缓存内容
            self._content_cache[skill_name] = content
            return content
        except Exception as e:
            print(f"[WARNING] 加载技能内容失败 {skill_name}: {e}")
            return None
    
    def load_skill(self, skill_name: str) -> Optional[Skill]:
        """
        加载完整的技能对象。
        
        包含元信息和完整内容。这是最完整的加载方式。
        
        参数:
            skill_name (str): 技能名称
        
        返回:
            Optional[Skill]: 完整的技能对象，失败返回 None
        
        流程:
            1. 加载元信息
            2. 加载完整内容
            3. 组装成 Skill 对象
        """
        # 加载元信息
        metadata = self.load_skill_metadata(skill_name)
        if not metadata:
            return None
        
        # 加载内容
        content = self.load_skill_content(skill_name)
        if not content:
            return None
        
        # 创建完整技能对象
        return Skill(
            name=metadata.name,
            description=metadata.description,
            content=content,
            path=metadata.path
        )
    
    def _parse_front_matter(self, content: str) -> dict:
        """
        解析 Markdown 文件的 front matter。
        
        Front matter 是 Markdown 文件开头的 YAML 格式元数据：
        ---
        name: 技能名称
        description: 技能描述
        ---
        
        参数:
            content (str): Markdown 文件内容
        
        返回:
            dict: 解析后的元数据字典
        
        解析规则:
            - 必须在文件开头
            - 用 --- 包围
            - 每行格式：key: value
        """
        # 正则表达式匹配 front matter
        # ^---\n 匹配开头的 ---
        # (.*?) 非贪婪匹配内容
        # \n--- 匹配结束的 ---
        pattern = r'^---\n(.*?)\n---'
        match = re.match(pattern, content, re.DOTALL)
        
        if not match:
            return {}
        
        front_matter = match.group(1)
        metadata = {}
        
        # 简单解析 key: value 格式
        for line in front_matter.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                # 去除空白和引号
                metadata[key.strip()] = value.strip().strip('"\'')
        
        return metadata
    
    def clear_cache(self):
        """
        清空内容缓存。
        
        用于释放内存或强制重新加载文件。
        """
        self._content_cache.clear()
