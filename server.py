
import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from typing import AsyncGenerator, Dict, Any, Optional
from fastapi import FastAPI, Request, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import Agent components from ag.py
from ag import (
    LLMTransport, 
    ToolExecutor, 
    SkillsLoader, 
    SkillsManager, 
    ConversationLogger, 
    AgentRuntime,
    # Import tools to register
    list_files, ListFilesArgs,
    read_file, ReadFileArgs,
    write_to_file, WriteToFileArgs,
    delete_file, DeleteFileArgs,
    search_files, SearchFilesArgs,
    edit_file, EditFileArgs,
    execute_command, ExecuteCommandArgs,
    browser_action, BrowserActionArgs,
    apply_diff, ApplyDiffArgs,
    ask_followup_question, AskFollowupQuestionArgs,
    attempt_completion, AttemptCompletionArgs,
    new_task, NewTaskArgs,
    switch_mode, SwitchModeArgs,
    update_todo_list, UpdateTodoListArgs,
    fetch_instructions, FetchInstructionsArgs,
    list_skills, ListSkillsArgs,
    search_skills, SearchSkillsArgs,
    get_skill, GetSkillArgs
)

# Import Auth components
from auth import router as auth_router, dependencies as auth_deps, models as auth_models

app = FastAPI()

# Init DB on startup
@app.on_event("startup")
def on_startup():
    auth_router.init_db()

# Enable CORS (Allows all origin for dev, consider restricting for prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Auth Router
app.include_router(auth_router.router)

# Mount static files
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Session Storage
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# Global State: User ID -> Runtime / Session ID
# In-memory storage
sessions = []
# Map: f"{user_id}:{session_id}" -> AgentRuntime
session_runtimes: Dict[str, Any] = {}
# Active session per user
active_sessions: Dict[int, str] = {}

# Load environment variables from .env file
load_dotenv()

# API Key Config
# For multi-user, using one system API key is typical for SaaS,
# or we could ask each user to provide one (future scope).
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "glm4.7")

def get_or_create_runtime(user_id: int, session_id: str):
    """Retrieve existing runtime for user/session or create a new one."""
    runtime_key = f"{user_id}:{session_id}"
    
    if runtime_key in session_runtimes:
        # Check if runtime still valid/needed?
        return session_runtimes[runtime_key]
    
    # Create new runtime
    transport = LLMTransport(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL, model=OPENAI_MODEL)
    
    skills_root = Path(".skills")
    skills_loader = SkillsLoader(skills_root)
    skills_manager = SkillsManager(skills_loader)

    executor = ToolExecutor()
    # Register tools
    executor.register(list_files, ListFilesArgs)
    executor.register(read_file, ReadFileArgs)
    executor.register(write_to_file, WriteToFileArgs)
    executor.register(delete_file, DeleteFileArgs)
    executor.register(search_files, SearchFilesArgs)
    executor.register(edit_file, EditFileArgs)
    executor.register(execute_command, ExecuteCommandArgs)
    executor.register(browser_action, BrowserActionArgs)
    executor.register(apply_diff, ApplyDiffArgs)
    executor.register(ask_followup_question, AskFollowupQuestionArgs)
    executor.register(attempt_completion, AttemptCompletionArgs)
    executor.register(new_task, NewTaskArgs)
    executor.register(switch_mode, SwitchModeArgs)
    executor.register(update_todo_list, UpdateTodoListArgs)
    executor.register(fetch_instructions, FetchInstructionsArgs)
    executor.register(list_skills, ListSkillsArgs)
    executor.register(search_skills, SearchSkillsArgs)
    executor.register(get_skill, GetSkillArgs)

    logger = ConversationLogger() # Each runtime gets its own logger instance (though writes to file based on logic)
    # Note: ConversationLogger default writes to 'logs/'. We might want to separate user logs too?
    # For now, we keep default behavior but runtime is isolated in memory.
    
    # Determine autosave path
    session_path = get_session_path(user_id, session_id)
    
    runtime = AgentRuntime(
        transport, 
        executor, 
        skills_manager=skills_manager, 
        logger=logger, 
        env="web",
        autosave_file=str(session_path) # Enable auto-save to this session file
    )
    
    # Check if we should load existing history (if file exists)
    if session_path.exists():
        try:
            runtime.context.load_history(str(session_path))
        except Exception:
            pass # Ignore load errors for empty/new

    session_runtimes[runtime_key] = runtime
    return runtime

def get_session_path(user_id: int, session_id: str):
    return SESSIONS_DIR / f"{user_id}_session_{session_id}.json"

def save_user_session(user_id: int):
    """Deprecated: Autosave is now active. This is kept for manual trigger if needed."""
    if user_id not in active_sessions:
        return
    sid = active_sessions[user_id]
    path = get_session_path(user_id, sid)
    runtime = get_or_create_runtime(user_id, sid)
    runtime.context.save_history(str(path))

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

# --- Session Management Endpoints ---

@app.get("/sessions")
async def list_sessions(current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """List sessions for the current user."""
    sessions = []
    if not SESSIONS_DIR.exists():
        return {"sessions": []}
    
    # Filter files starting with "{user_id}_session_"
    prefix = f"{current_user.id}_session_"
    for f in SESSIONS_DIR.glob(f"{prefix}*.json"):
        sid = f.stem.replace(prefix, "")
        stat = f.stat()
        sessions.append({
            "id": sid,
            "timestamp": stat.st_mtime,
            "filename": f.name
        })
    sessions.sort(key=lambda x: x["timestamp"], reverse=True)
    
    # Get active session ID for this user
    cur_sid = active_sessions.get(current_user.id, None)
    return {"sessions": sessions, "current_session_id": cur_sid}

@app.post("/sessions/new")
async def new_session(current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """Start a fresh session for current user."""
    from datetime import datetime
    new_sid = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Initialize runtime for this new session
    runtime = get_or_create_runtime(current_user.id, new_sid)
    runtime.context.reset() # Should be fresh anyway
    runtime.context.save_history(str(get_session_path(current_user.id, new_sid))) # Initial save
    
    active_sessions[current_user.id] = new_sid
    
    return {"id": new_sid, "message": "New session started"}

@app.post("/sessions/{session_id}/load")
async def load_session(session_id: str, current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """Load a specific session for current user."""
    path = get_session_path(current_user.id, session_id)
    if not path.exists():
        return {"error": "Session not found or permission denied"}
    
    # Get separate runtime for this session (it will auto-load inside get_or_create)
    runtime = get_or_create_runtime(current_user.id, session_id)
    # Force reload just in case? No, get_or_create handles it for new runtimes. 
    # If runtime already existed in memory, it should be up to date.
    
    active_sessions[current_user.id] = session_id
    
    msgs = runtime.context.history[1:] if len(runtime.context.history) > 0 else []
    return {"id": session_id, "history": msgs}

# ------------------------------------

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, current_user: auth_models.User = Depends(auth_deps.get_current_active_user)):
    """
    Streaming response using SSE, protected by Auth.
    """
    # Determine Session ID
    session_id = request.session_id
    if not session_id:
        session_id = active_sessions.get(current_user.id)
    
    if not session_id:
        # Auto-create if no active session
        from datetime import datetime
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        active_sessions[current_user.id] = session_id
        
    # Get Isolated Runtime
    runtime = get_or_create_runtime(current_user.id, session_id)

    async def event_generator():
        try:
            async for event in runtime.step(request.message):
                data = json.dumps(event)
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.01)
            
            # Auto-save after turn completion
            save_user_session(current_user.id)
            
        except Exception as e:
            error_event = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    print("Starting Web Server on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)

