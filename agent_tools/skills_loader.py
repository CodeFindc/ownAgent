"""
技能加载器模块
负责从 .skills 目录加载技能的元信息和完整内容
"""

import os
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """技能元信息模型（轻量级，用于检索）"""
    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="技能描述")
    path: Path = Field(..., description="技能文件路径")


class Skill(BaseModel):
    """技能完整数据模型（包含完整内容）"""
    name: str = Field(..., description="技能名称")
    description: str = Field(..., description="技能描述")
    content: str = Field(..., description="技能完整内容（markdown）")
    path: Path = Field(..., description="技能文件路径")
    loaded_at: datetime = Field(default_factory=datetime.now, description="加载时间")


class SkillsLoader:
    """技能加载器，从 .skills 目录加载技能元信息和完整内容"""
    
    def __init__(self, skills_root: Path):
        """初始化加载器
        
        Args:
            skills_root: 技能根目录路径（默认为 .skills）
        """
        self.skills_root = Path(skills_root)
        self._content_cache: dict[str, str] = {}  # 内容缓存
        
    def load_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        """加载单个技能的元信息（仅 name 和 description）
        
        Args:
            skill_name: 技能名称
            
        Returns:
            SkillMetadata 对象，如果加载失败返回 None
        """
        skill_path = self.skills_root / skill_name / "SKILL.md"
        
        if not skill_path.exists():
            return None
            
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 front matter
            metadata = self._parse_front_matter(content)
            
            if not metadata.get('name') or not metadata.get('description'):
                return None
                
            return SkillMetadata(
                name=metadata['name'],
                description=metadata['description'],
                path=skill_path
            )
        except Exception as e:
            print(f"[WARNING] 加载技能元信息失败 {skill_name}: {e}")
            return None
    
    def load_all_metadata(self) -> List[SkillMetadata]:
        """加载所有技能的元信息（不加载完整内容）
        
        Returns:
            技能元信息列表
        """
        metadata_list = []
        
        if not self.skills_root.exists():
            print(f"[INFO] 技能目录不存在: {self.skills_root}")
            return metadata_list
        
        # 遍历技能目录
        for skill_dir in self.skills_root.iterdir():
            if not skill_dir.is_dir():
                continue
                
            skill_name = skill_dir.name
            metadata = self.load_skill_metadata(skill_name)
            
            if metadata:
                metadata_list.append(metadata)
                print(f"[INFO] 加载技能元信息: {metadata.name}")
        
        return metadata_list
    
    def load_skill_content(self, skill_name: str) -> Optional[str]:
        """加载技能的完整内容（按需加载）
        
        Args:
            skill_name: 技能名称
            
        Returns:
            技能的完整 markdown 内容
        """
        # 检查缓存
        if skill_name in self._content_cache:
            return self._content_cache[skill_name]
        
        skill_path = self.skills_root / skill_name / "SKILL.md"
        
        if not skill_path.exists():
            return None
            
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 缓存内容
            self._content_cache[skill_name] = content
            return content
        except Exception as e:
            print(f"[WARNING] 加载技能内容失败 {skill_name}: {e}")
            return None
    
    def load_skill(self, skill_name: str) -> Optional[Skill]:
        """加载完整的技能对象（包含元信息和内容）
        
        Args:
            skill_name: 技能名称
            
        Returns:
            Skill 对象，如果加载失败返回 None
        """
        metadata = self.load_skill_metadata(skill_name)
        if not metadata:
            return None
        
        content = self.load_skill_content(skill_name)
        if not content:
            return None
        
        return Skill(
            name=metadata.name,
            description=metadata.description,
            content=content,
            path=metadata.path
        )
    
    def _parse_front_matter(self, content: str) -> dict:
        """解析 markdown 文件的 front matter
        
        Args:
            content: markdown 文件内容
            
        Returns:
            解析后的元数据字典
        """
        # 匹配 YAML front matter 格式
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
                metadata[key.strip()] = value.strip().strip('"\'')
        
        return metadata
    
    def clear_cache(self):
        """清空内容缓存"""
        self._content_cache.clear()
