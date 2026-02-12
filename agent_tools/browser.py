import base64
from typing import Optional, Literal
from pydantic import BaseModel, Field
from agent_tools.base import ToolContext, ToolResult, validate_path

# Try importing playwright
try:
    from playwright.async_api import async_playwright, Page, BrowserContext, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class BrowserActionArgs(BaseModel):
    action: Literal[
        "launch", "click", "hover", "type", "press", 
        "scroll_down", "scroll_up", "resize", "close", "screenshot"
    ] = Field(..., description="Browser action to perform")
    url: Optional[str] = Field(None, description="URL to open when performing the launch action; must include protocol")
    coordinate: Optional[str] = Field(None, description="Screen coordinate for hover or click actions in format 'x,y@WIDTHxHEIGHT' where x,y is the target position on the screenshot image and WIDTHxHEIGHT is the exact pixel dimensions of the screenshot image (not the browser viewport). Example: '450,203@900x600' means click at (450,203) on a 900x600 screenshot. The coordinates will be automatically scaled to match the actual viewport dimensions.")
    size: Optional[str] = Field(None, description="Viewport dimensions for the resize action in format 'WIDTHxHEIGHT' or 'WIDTH,HEIGHT'. Example: '1280x800' or '1280,800'")
    text: Optional[str] = Field(None, description="Text to type when performing the type action, or key name to press when performing the press action (e.g., 'Enter', 'Tab', 'Escape')")
    path: Optional[str] = Field(None, description="File path where the screenshot should be saved (relative to workspace). Required for screenshot action. Supports .png, .jpeg, and .webp extensions. Example: 'screenshots/result.png'")

def _get_page(ctx: ToolContext) -> Optional['Page']:
    """
    Get current page from context.
    """
    if not ctx.browser_session:
        return None
    return ctx.browser_session.get('page')

async def _ensure_browser(ctx: ToolContext):
    """
    Ensure browser is launched.
    (异步确保浏览器已启动)
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright 未安装 / Playwright not installed")
        
    if ctx.browser_session is None:
        # 使用 async_playwright() 避免阻塞主线程循环
        # Use async_playwright() to avoid blocking the main event loop
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True) # Default headless
        # 创建上下文和页面也需要 await
        context = await browser.new_context()
        page = await context.new_page()
        ctx.browser_session = {
            'playwright': p,
            'browser': browser,
            'context': context,
            'page': page
        }

async def browser_action(ctx: ToolContext, args: BrowserActionArgs) -> ToolResult:
    """
    Request to interact with a Puppeteer-controlled browser. 
    (异步执行浏览器操作。必须使用 async/await 以兼容 FastAPI 的事件循环)

    This tool is particularly useful for web development tasks as it allows you to launch a browser, navigate to pages, interact with elements through clicks and keyboard input, and capture the results through screenshots and console logs. Use it at key stages of web development tasks - such as after implementing new features, making substantial changes, when troubleshooting issues, or to verify the result of your work. Analyze the provided screenshots to ensure correct rendering or identify errors, and review console logs for runtime issues.

    The user may ask generic non-development tasks (such as "what's the latest news" or "look up the weather"), in which case you might use this tool to complete the task if it makes sense to do so, rather than trying to create a website or using curl to answer the question. However, if an available MCP server tool or resource can be used instead, you should prefer to use it over browser_action.

    Browser Session Lifecycle:
    - Browser sessions start with launch and end with close
    - The session remains active across multiple messages and tool uses
    - You can use other tools while the browser session is active - it will stay open in the background
    """
    if not PLAYWRIGHT_AVAILABLE:
        return ToolResult(success=False, output="错误：Playwright 库未安装 / Error: Playwright library not installed")

    try:
        # Handle launch
        if args.action == "launch":
            if ctx.browser_session:
                # Close old session
                await ctx.browser_session['browser'].close()
                await ctx.browser_session['playwright'].stop()
                ctx.browser_session = None
            
            await _ensure_browser(ctx)
            page = _get_page(ctx)
            if args.url:
                await page.goto(args.url)
            return ToolResult(success=True, output=f"浏览器已启动并访问 {args.url} / Browser launched and visited {args.url}")

        # For other actions, ensure browser is running
        if not ctx.browser_session:
             return ToolResult(success=False, output="错误：浏览器未运行。请先使用 'launch' 操作。 / Error: Browser not running. Use 'launch' first.")
        
        page = _get_page(ctx)

        if args.action == "close":
            await ctx.browser_session['browser'].close()
            await ctx.browser_session['playwright'].stop()
            ctx.browser_session = None
            return ToolResult(success=True, output="浏览器已关闭 / Browser closed")

        elif args.action == "click":
            if args.coordinate:
                try:
                    coord_part, size_part = args.coordinate.split('@')
                    x, y = map(int, coord_part.split(','))
                    await page.mouse.click(x, y)
                except ValueError:
                    return ToolResult(success=False, output="错误：坐标格式无效 / Error: Invalid coordinate format")
            else:
                return ToolResult(success=False, output="错误：点击操作需要坐标 / Error: Click action requires coordinate")

        elif args.action == "hover":
            if args.coordinate:
                try:
                    coord_part, size_part = args.coordinate.split('@')
                    x, y = map(int, coord_part.split(','))
                    await page.mouse.move(x, y)
                except ValueError:
                    return ToolResult(success=False, output="错误：坐标格式无效 / Error: Invalid coordinate format")
            else:
                 return ToolResult(success=False, output="错误：悬停操作需要坐标 / Error: Hover action requires coordinate")

        elif args.action == "type":
            if args.text:
                await page.keyboard.type(args.text)
            else:
                return ToolResult(success=False, output="错误：输入操作需要文本 / Error: Type action requires text")

        elif args.action == "press":
            if args.text:
                await page.keyboard.press(args.text)
            else:
                return ToolResult(success=False, output="错误：按键操作需要键名 / Error: Press action requires key name")

        elif args.action == "scroll_down":
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            
        elif args.action == "scroll_up":
            await page.evaluate("window.scrollBy(0, -window.innerHeight)")
            
        elif args.action == "resize":
            if args.size:
                try:
                    if 'x' in args.size:
                        w, h = map(int, args.size.split('x'))
                    else:
                        w, h = map(int, args.size.split(','))
                    await page.set_viewport_size({"width": w, "height": h})
                except ValueError:
                    return ToolResult(success=False, output="错误：尺寸格式无效 / Error: Invalid size format")
            else:
                return ToolResult(success=False, output="错误：调整大小操作需要尺寸 / Error: Resize action requires size")

        elif args.action == "screenshot":
            if args.path:
                target_path = validate_path(args.path, ctx.workspace_root)
                # Ensure directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(target_path))
                return ToolResult(success=True, output=f"截图已保存到 {args.path} / Screenshot saved to {args.path}")
            else:
                return ToolResult(success=False, output="错误：截图操作需要路径 / Error: Screenshot action requires path")

        return ToolResult(success=True, output=f"成功执行操作: {args.action} / Successfully executed: {args.action}")

    except Exception as e:
        return ToolResult(success=False, output=f"浏览器操作失败 / Browser action failed: {str(e)}")
