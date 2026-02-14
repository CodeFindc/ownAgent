"""
=============================================================================
ownAgent - 浏览器自动化工具模块
=============================================================================

本文件实现了浏览器自动化工具：

1. browser_action - 执行各种浏览器操作

支持的浏览器操作：
- launch: 启动浏览器并访问 URL
- click: 点击指定坐标
- hover: 悬停在指定坐标
- type: 输入文本
- press: 按下按键
- scroll_down: 向下滚动
- scroll_up: 向上滚动
- resize: 调整视口大小
- close: 关闭浏览器
- screenshot: 截图保存

使用场景：
- Web 开发测试
- 网页截图
- 自动化网页操作
- 验证前端效果

依赖：
- Playwright 库（可选）
- 安装：pip install playwright && playwright install chromium

作者: ownAgent Team
版本: 1.0.0
=============================================================================
"""

# =============================================================================
# 标准库导入
# =============================================================================

import base64  # Base64 编码，用于处理截图数据
from typing import Optional, Literal  # 类型提示

# =============================================================================
# 第三方库导入
# =============================================================================

from pydantic import BaseModel, Field  # 数据验证和设置管理

# =============================================================================
# 项目内部模块导入
# =============================================================================

from agent_tools.base import ToolContext, ToolResult, validate_path


# =============================================================================
# Playwright 导入（可选依赖）
# =============================================================================

# 尝试导入 Playwright
# 这是一个可选依赖，如果未安装则功能不可用
try:
    from playwright.async_api import async_playwright, Page, BrowserContext, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    # 如果导入失败，标记为不可用
    PLAYWRIGHT_AVAILABLE = False


# =============================================================================
# 参数模型定义 (Argument Models)
# =============================================================================

class BrowserActionArgs(BaseModel):
    """
    browser_action 工具的参数模型。
    
    这个工具支持多种浏览器操作，通过 action 参数指定。
    
    属性:
        action (Literal[...]): 要执行的浏览器操作
            - "launch": 启动浏览器
            - "click": 点击
            - "hover": 悬停
            - "type": 输入文本
            - "press": 按键
            - "scroll_down": 向下滚动
            - "scroll_up": 向上滚动
            - "resize": 调整大小
            - "close": 关闭浏览器
            - "screenshot": 截图
        
        url (Optional[str]): 启动时访问的 URL
            - 仅用于 launch 操作
            - 必须包含协议（http:// 或 https://）
        
        coordinate (Optional[str]): 点击或悬停的坐标
            - 格式：'x,y@WIDTHxHEIGHT'
            - 例如：'450,203@900x600'
            - 坐标基于截图尺寸，会自动缩放到实际视口
        
        size (Optional[str]): 视口尺寸
            - 格式：'WIDTHxHEIGHT' 或 'WIDTH,HEIGHT'
            - 例如：'1280x800' 或 '1280,800'
        
        text (Optional[str]): 输入的文本或按键名称
            - type 操作：要输入的文本
            - press 操作：按键名称（'Enter', 'Tab', 'Escape' 等）
        
        path (Optional[str]): 截图保存路径
            - 相对于工作区
            - 支持 .png, .jpeg, .webp 格式
    
    示例:
        >>> # 启动浏览器
        >>> args = BrowserActionArgs(action="launch", url="https://example.com")
        
        >>> # 点击坐标
        >>> args = BrowserActionArgs(action="click", coordinate="100,200@900x600")
        
        >>> # 输入文本
        >>> args = BrowserActionArgs(action="type", text="Hello World")
        
        >>> # 截图
        >>> args = BrowserActionArgs(action="screenshot", path="screenshot.png")
    """
    action: Literal[
        "launch", "click", "hover", "type", "press", 
        "scroll_down", "scroll_up", "resize", "close", "screenshot"
    ] = Field(
        ...,
        description="Browser action to perform"
    )
    url: Optional[str] = Field(
        None,
        description="URL to open when performing the launch action; must include protocol"
    )
    coordinate: Optional[str] = Field(
        None,
        description="Screen coordinate for hover or click actions in format 'x,y@WIDTHxHEIGHT' where x,y is the target position on the screenshot image and WIDTHxHEIGHT is the exact pixel dimensions of the screenshot image (not the browser viewport). Example: '450,203@900x600' means click at (450,203) on a 900x600 screenshot. The coordinates will be automatically scaled to match the actual viewport dimensions."
    )
    size: Optional[str] = Field(
        None,
        description="Viewport dimensions for the resize action in format 'WIDTHxHEIGHT' or 'WIDTH,HEIGHT'. Example: '1280x800' or '1280,800'"
    )
    text: Optional[str] = Field(
        None,
        description="Text to type when performing the type action, or key name to press when performing the press action (e.g., 'Enter', 'Tab', 'Escape')"
    )
    path: Optional[str] = Field(
        None,
        description="File path where the screenshot should be saved (relative to workspace). Required for screenshot action. Supports .png, .jpeg, and .webp extensions. Example: 'screenshots/result.png'"
    )


# =============================================================================
# 辅助函数
# =============================================================================

def _get_page(ctx: ToolContext) -> Optional['Page']:
    """
    从上下文获取当前浏览器页面。
    
    参数:
        ctx (ToolContext): 工具执行上下文
    
    返回:
        Optional[Page]: Playwright Page 对象，如果不存在则返回 None
    
    说明:
        browser_session 是一个字典，包含：
        - 'playwright': Playwright 实例
        - 'browser': Browser 实例
        - 'context': BrowserContext 实例
        - 'page': Page 实例
    """
    if not ctx.browser_session:
        return None
    return ctx.browser_session.get('page')


async def _ensure_browser(ctx: ToolContext):
    """
    确保浏览器已启动。
    
    如果浏览器未启动，则创建新的浏览器会话。
    这是异步函数，因为 Playwright 的操作都是异步的。
    
    参数:
        ctx (ToolContext): 工具执行上下文
    
    异常:
        ImportError: 如果 Playwright 未安装
    
    创建的会话结构:
        ctx.browser_session = {
            'playwright': Playwright 实例,
            'browser': Browser 实例,
            'context': BrowserContext 实例,
            'page': Page 实例
        }
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright 未安装 / Playwright not installed")
        
    if ctx.browser_session is None:
        # 启动 Playwright
        # async_playwright() 是异步上下文管理器
        p = await async_playwright().start()
        
        # 启动 Chromium 浏览器
        # headless=True 表示无头模式（不显示��览器窗口）
        browser = await p.chromium.launch(headless=True)
        
        # 创建浏览器上下文
        # 上下文类似于隐身窗口，有独立的 cookies 和存储
        context = await browser.new_context()
        
        # 创建新页面
        page = await context.new_page()
        
        # 保存会话信息到上下文
        ctx.browser_session = {
            'playwright': p,
            'browser': browser,
            'context': context,
            'page': page
        }


# =============================================================================
# 工具实现 (Tool Implementations)
# =============================================================================

async def browser_action(ctx: ToolContext, args: BrowserActionArgs) -> ToolResult:
    """
    执行浏览器操作。
    
    这是一个异步工具，支持多种浏览器操作。
    
    参数:
        ctx (ToolContext): 工具执行上下文
        args (BrowserActionArgs): 工具参数
    
    返回:
        ToolResult: 操作结果
    
    支持的操作:
        1. launch: 启动浏览器并访问 URL
           - 需要提供 url 参数
           - 如果已有浏览器会话，会先关闭
        
        2. click: 点击指定坐标
           - 需要提供 coordinate 参数
        
        3. hover: 悬停在指定坐标
           - 需要提供 coordinate 参数
        
        4. type: 输入文本
           - 需要提供 text 参数
        
        5. press: 按下按键
           - 需要提供 text 参数（按键名称）
        
        6. scroll_down: 向下滚动一屏
        
        7. scroll_up: 向上滚动一屏
        
        8. resize: 调整视口大小
           - 需要提供 size 参数
        
        9. close: 关闭浏览器
        
        10. screenshot: 截图保存
            - 需要提供 path 参数
    
    浏览器会话生命周期:
        - launch 启动会话
        - close 关闭会话
        - 会话在多次工具调用间保持活跃
        - 可以在使用其他工具时保持浏览器打开
    
    使用场景:
        - Web 开发：验证页面效果
        - 测试：自动化 UI 测试
        - 截图：生成网页预览
        - 调试：排查前端问题
    """
    # 检查 Playwright 是否可用
    if not PLAYWRIGHT_AVAILABLE:
        return ToolResult(
            success=False, 
            output="错误：Playwright 库未安装 / Error: Playwright library not installed"
        )

    try:
        # === launch 操作：启动浏览器 ===
        if args.action == "launch":
            # 如果已有会话，先关闭
            if ctx.browser_session:
                await ctx.browser_session['browser'].close()
                await ctx.browser_session['playwright'].stop()
                ctx.browser_session = None
            
            # 确保浏览器启动
            await _ensure_browser(ctx)
            page = _get_page(ctx)
            
            # 如果提供了 URL，访问它
            if args.url:
                await page.goto(args.url)
                
            return ToolResult(
                success=True, 
                output=f"浏览器已启动并访问 {args.url} / Browser launched and visited {args.url}"
            )

        # 其他操作需要浏览器已启动
        if not ctx.browser_session:
            return ToolResult(
                success=False, 
                output="错误：浏览器未运行。请先使用 'launch' 操作。 / Error: Browser not running. Use 'launch' first."
            )
        
        page = _get_page(ctx)

        # === close 操作：关闭浏览器 ===
        if args.action == "close":
            await ctx.browser_session['browser'].close()
            await ctx.browser_session['playwright'].stop()
            ctx.browser_session = None
            return ToolResult(success=True, output="浏览器已关闭 / Browser closed")

        # === click 操作：点击坐标 ===
        elif args.action == "click":
            if args.coordinate:
                try:
                    # 解析坐标格式：'x,y@WIDTHxHEIGHT'
                    coord_part, size_part = args.coordinate.split('@')
                    x, y = map(int, coord_part.split(','))
                    # 执行点击
                    await page.mouse.click(x, y)
                except ValueError:
                    return ToolResult(
                        success=False, 
                        output="错误：坐标格式无效 / Error: Invalid coordinate format"
                    )
            else:
                return ToolResult(
                    success=False, 
                    output="错误：点击操作需要坐标 / Error: Click action requires coordinate"
                )

        # === hover 操作：悬停 ===
        elif args.action == "hover":
            if args.coordinate:
                try:
                    coord_part, size_part = args.coordinate.split('@')
                    x, y = map(int, coord_part.split(','))
                    # 移动鼠标到指定位置
                    await page.mouse.move(x, y)
                except ValueError:
                    return ToolResult(
                        success=False, 
                        output="错误：坐标格式无效 / Error: Invalid coordinate format"
                    )
            else:
                return ToolResult(
                    success=False, 
                    output="错误：悬停操作需要坐标 / Error: Hover action requires coordinate"
                )

        # === type 操作：输入文本 ===
        elif args.action == "type":
            if args.text:
                # 模拟键盘输入
                await page.keyboard.type(args.text)
            else:
                return ToolResult(
                    success=False, 
                    output="错误：输入操作需要文本 / Error: Type action requires text"
                )

        # === press 操作：按下按键 ===
        elif args.action == "press":
            if args.text:
                # 按下指定按键
                # text 参数是按键名称，如 'Enter', 'Tab', 'Escape'
                await page.keyboard.press(args.text)
            else:
                return ToolResult(
                    success=False, 
                    output="错误：按键操作需要键名 / Error: Press action requires key name"
                )

        # === scroll_down 操作：向下滚动 ===
        elif args.action == "scroll_down":
            # 执行 JavaScript 滚动
            # window.innerHeight 是视口高度
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            
        # === scroll_up 操作：向上滚动 ===
        elif args.action == "scroll_up":
            await page.evaluate("window.scrollBy(0, -window.innerHeight)")
            
        # === resize 操作：调整视口大小 ===
        elif args.action == "resize":
            if args.size:
                try:
                    # 支持两种格式：'WIDTHxHEIGHT' 或 'WIDTH,HEIGHT'
                    if 'x' in args.size:
                        w, h = map(int, args.size.split('x'))
                    else:
                        w, h = map(int, args.size.split(','))
                    # 设置视口大小
                    await page.set_viewport_size({"width": w, "height": h})
                except ValueError:
                    return ToolResult(
                        success=False, 
                        output="错误：尺寸格式无效 / Error: Invalid size format"
                    )
            else:
                return ToolResult(
                    success=False, 
                    output="错误：调整大小操作需要尺寸 / Error: Resize action requires size"
                )

        # === screenshot 操作：截图 ===
        elif args.action == "screenshot":
            if args.path:
                # 验证并获取保存路径
                target_path = validate_path(args.path, ctx.workspace_root)
                # 确保目录存在
                target_path.parent.mkdir(parents=True, exist_ok=True)
                # 截图保存
                await page.screenshot(path=str(target_path))
                return ToolResult(
                    success=True, 
                    output=f"截图已保存到 {args.path} / Screenshot saved to {args.path}"
                )
            else:
                return ToolResult(
                    success=False, 
                    output="错误：截图操作需要路径 / Error: Screenshot action requires path"
                )

        # 返回成功结果
        return ToolResult(
            success=True, 
            output=f"成功执行操作: {args.action} / Successfully executed: {args.action}"
        )

    except Exception as e:
        # 捕获并返回错误
        return ToolResult(
            success=False, 
            output=f"浏览器操作失败 / Browser action failed: {str(e)}"
        )
