from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field

# =============================================================================
# JSON-RPC 2.0 Models
# =============================================================================

class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 请求模型"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 响应模型"""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

class JsonRpcNotification(BaseModel):
    """JSON-RPC 2.0 通知模型"""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None

# =============================================================================
# MCP Protocol Models
# =============================================================================

class Implementation(BaseModel):
    """客户端/服务器实现信息"""
    name: str
    version: str

class ClientCapabilities(BaseModel):
    """客户端能力声明"""
    experimental: Optional[Dict[str, Any]] = None
    sampling: Optional[Dict[str, Any]] = None
    roots: Optional[Dict[str, Any]] = None

class InitializeParams(BaseModel):
    """初始化请求参数"""
    protocolVersion: str = "2024-11-05"
    capabilities: ClientCapabilities
    clientInfo: Implementation

class ServerCapabilities(BaseModel):
    """服务器能力声明"""
    experimental: Optional[Dict[str, Any]] = None
    logging: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    tools: Optional[Dict[str, Any]] = None

class InitializeResult(BaseModel):
    """初始化响应结果"""
    protocolVersion: str
    capabilities: ServerCapabilities
    serverInfo: Implementation

class Tool(BaseModel):
    """工具定义"""
    name: str
    description: Optional[str] = None
    inputSchema: Dict[str, Any]  # JSON Schema

class ListToolsResult(BaseModel):
    """工具列表响应结果"""
    tools: List[Tool]
    nextCursor: Optional[str] = None

class CallToolParams(BaseModel):
    """调用工具请求参数"""
    name: str
    arguments: Optional[Dict[str, Any]] = None

class ToolContent(BaseModel):
    """工具执行结果内容"""
    type: Literal["text", "image", "resource"]
    text: Optional[str] = None
    data: Optional[str] = None
    mimeType: Optional[str] = None
    resource: Optional[Dict[str, Any]] = None

class CallToolResult(BaseModel):
    """工具执行响应结果"""
    content: List[Dict[str, Any]]
    isError: bool = False
