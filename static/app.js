document.addEventListener('DOMContentLoaded', () => {
    // Debug: Remove loading overlay
    const loader = document.getElementById('app-loading');
    if (loader) loader.style.display = 'none';

    // [DOM Element Selection / 获取页面元素]
    // These variables store references to HTML elements so we can manipulate them later.
    // 这些变量存储了对 HTML 元素的引用，以便我们稍后操作它们。
    const messagesContainer = document.getElementById('messages'); // The chat history area / 聊天记录区域
    const userInput = document.getElementById('userInput');        // The input box / 输入框
    const sendBtn = document.getElementById('sendBtn');            // The send button / 发送按钮
    const sessionListEl = document.getElementById('sessionList');  // The sidebar history list / 侧边栏历史列表
    const newChatBtn = document.getElementById('newChatBtn');      // "New Chat" button / "新建聊天"按钮

    // Auth UI Elements / 认证相关的界面元素
    // Auth UI Elements
    const userProfileEl = document.getElementById('userProfile');
    const userAvatar = document.getElementById('userAvatar'); // Dashboard View
    const userAvatarSidebar = document.getElementById('userAvatarSidebar'); // Sidebar View (if distinct)
    const userNameDisplay = document.getElementById('userNameDisplay');
    const userDropdown = document.getElementById('userDropdown');
    const logoutBtn = document.getElementById('logoutBtn');
    const navAdminUsers = document.getElementById('navAdminUsers');
    const navAdminSettings = document.getElementById('navAdminSettings');

    // Logo Elements
    const logoIcon = document.getElementById('logoIcon');
    const logoText = document.getElementById('logoText');

    // State
    let accessToken = localStorage.getItem('access_token');
    let currentUser = null;
    let activeSessionId = null;

    // --- Initialization ---
    // 1. Load System Settings (Logo) & Language
    loadSystemSettings();

    // Init i18n
    if (typeof applyTranslations === 'function') {
        const savedLang = localStorage.getItem('app_language');
        if (savedLang) setLanguage(savedLang);
    }

    // 2. Check Auth
    if (accessToken) {
        checkAuthStatus();
    } else {
        window.location.href = '/static/login.html';
    }

    async function loadSystemSettings() {
        try {
            // Public endpoint to get settings
            const res = await fetch('/auth/settings');
            if (res.ok) {
                const settings = await res.json();
                const siteName = settings.find(s => s.key === 'site_name');
                const siteLogoText = settings.find(s => s.key === 'site_logo_text');

                if (siteName && logoText) logoText.textContent = siteName.value;
                if (siteLogoText && logoIcon) logoIcon.textContent = siteLogoText.value;
            }
        } catch (e) {
            console.error("Failed to load settings:", e);
        }
    }

    async function checkAuthStatus() {
        try {
            const user = await authFetch('/auth/users/me');
            currentUser = user;
            updateUIForLoggedIn(user);
            await loadSessions();
        } catch (e) {
            console.error("Auth check failed:", e);
            logout();
        }
    }

    // User Profile Interaction
    if (userProfileEl) {
        // Toggle dropdown on click (or could be hover via CSS, but JS toggle is safer for touch)
        // CSS handles hover, but let's ensure clicking doesn't break it or does something useful
        // actually, CSS :hover handling is sufficient for desktop.
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            logout();
        });
    }

    function logout() {
        accessToken = null;
        currentUser = null;
        localStorage.removeItem('access_token'); // Delete token from storage
        window.location.href = '/static/login.html'; // Redirect to login
    }

    function updateUIForLoggedIn(user) {
        if (userProfileEl) userProfileEl.style.display = 'flex';
        if (userNameDisplay) userNameDisplay.textContent = user.username;

        // Avatar Logic
        const avatarUrl = user.avatar_url;
        const els = [userAvatar, userAvatarSidebar, document.getElementById('userAvatar')]; // Handle potential duplicates or missing IDs

        els.forEach(el => {
            if (!el) return;
            if (avatarUrl) {
                el.textContent = '';
                el.style.backgroundImage = `url('${avatarUrl}')`;
                el.style.backgroundSize = 'cover';
                el.style.backgroundPosition = 'center';
            } else {
                el.textContent = user.username.charAt(0).toUpperCase();
                el.style.backgroundImage = 'none';
            }
        });

        // Show Admin Links
        if (user.role === 'admin') {
            if (navAdminUsers) navAdminUsers.style.display = 'block';
            if (navAdminSettings) navAdminSettings.style.display = 'block'; // New
        }

        // Welcome message if no chat history
        if (!activeSessionId && messagesContainer) { // Added guard for messagesContainer
            messagesContainer.innerHTML = `
            <div class="message system">
                <div class="avatar">AG</div>
                <div class="content">
                    ${(window.t ? window.t('type_message') : 'Hello')} ${user.username}! ${(window.t ? window.t('create_user') : 'Create a new chat')}?
                </div>
            </div>`;
        }
    }

    // --- Authenticated Fetch Wrapper / 认证请求包装器 ---
    // A helper to send requests with the Access Token automatically.
    // 一个辅助函数，用于自动带上 Access Token 发送请求。
    // If the token is invalid (401), it forces logout.
    // 如果 token 无效 (401)，它会强制注销。
    async function authFetch(url, options = {}) {
        if (!options.headers) options.headers = {};
        if (accessToken) {
            // Add "Authorization: Bearer <token>" header
            // 添加授权头
            options.headers['Authorization'] = `Bearer ${accessToken}`;
        }

        const res = await fetch(url, options); // Native fetch / 原生 fetch 请求
        if (res.status === 401) {
            logout(); // Token expired or invalid / Token 过期或无效
            throw new Error('Unauthorized');
        }
        // Helper: if response is JSON, parse it automatically
        // 辅助功能：如果响应是 JSON，自动解析它
        if (res.status !== 204 && res.headers.get('content-type')?.includes('application/json')) {
            return await res.json();
        }
        return res;
    }


    // --- Core Logic (Refactored to use authFetch where appropriate) ---

    // --- UI Interaction Logic / 界面交互逻辑 ---

    // 1. Auto-resize textarea inputs
    // 当这在输入框打字时，自动调整高度，防止文字被遮住
    userInput.addEventListener('input', function () {
        this.style.height = 'auto'; // Reset height first / 先重置高度
        this.style.height = (this.scrollHeight) + 'px'; // Set to scroll height / 设置为内容实际高度
    });

    // 2. Handle Enter Key
    // 监听 "回车键" 按下事件
    // --- Event Listeners / 事件监听器 ---

    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    if (userInput) {
        userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Auto-resize textarea
        userInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }

    if (newChatBtn) {
        newChatBtn.addEventListener('click', () => {
            // ... new chat logic
            // For now, new chat just reloads with no session? 
            // Or calls createNewSession
            createNewSession();
        });
    }

    async function loadSessions() {
        try {
            console.log("[DEBUG] Fetching sessions...");
            const data = await authFetch('/sessions');
            console.log("[DEBUG] Sessions data:", data);

            const sessions = data.sessions || [];

            // Set active session if not set locally but provided by server
            if (!activeSessionId && data.current_session_id) {
                console.log("[DEBUG] Setting active session from server:", data.current_session_id);
                activeSessionId = data.current_session_id;
            }

            if (sessionListEl) {
                sessionListEl.innerHTML = '';

                if (sessions.length === 0) {
                    sessionListEl.innerHTML = `<div style="padding:10px; color:#666; font-size:0.9em; text-align:center;">${window.t ? window.t('no_history') : 'No history'}</div>`;
                    return;
                }

                sessions.forEach(session => {
                    const div = document.createElement('div');
                    div.className = 'session-item';
                    div.dataset.id = session.id;

                    // Active state
                    if (session.id === activeSessionId) {
                        div.classList.add('active');
                    }

                    // Session Title
                    const titleSpan = document.createElement('span');
                    titleSpan.className = 'session-title';
                    titleSpan.textContent = session.title || "Session " + session.id.substring(0, 8);
                    titleSpan.onclick = () => switchSession(session.id); // Click title to load

                    // Three Dots Menu Trigger
                    const menuTrigger = document.createElement('div');
                    menuTrigger.className = 'session-menu-trigger';
                    menuTrigger.innerHTML = '⋮';
                    menuTrigger.onclick = (e) => {
                        e.stopPropagation();
                        toggleSessionMenu(session.id);
                    };

                    // Context Menu (Hidden by default)
                    const menu = document.createElement('div');
                    menu.className = 'session-context-menu';
                    menu.id = `session-menu-${session.id}`;

                    // Inline Delete Confirmation
                    const deleteBtn = document.createElement('div');
                    deleteBtn.className = 'context-menu-item danger delete-btn';
                    deleteBtn.textContent = window.t ? window.t('delete') : 'Delete';
                    deleteBtn.onclick = (e) => {
                        e.stopPropagation();
                        // Check against translated text or original
                        const delText = window.t ? window.t('delete') : 'Delete';
                        if (deleteBtn.textContent === delText) {
                            deleteBtn.textContent = window.t ? window.t('delete_confirm_short') : 'Confirm?';
                            deleteBtn.style.background = 'var(--error)';
                            deleteBtn.style.color = 'white';
                        } else {
                            deleteSession(session.id);
                        }
                    };

                    menu.appendChild(deleteBtn);

                    div.appendChild(titleSpan);
                    div.appendChild(menuTrigger);
                    div.appendChild(menu);
                    sessionListEl.appendChild(div);
                });
            }
        } catch (e) {
            console.error("Failed to load sessions:", e);
        }
    }

    function toggleSessionMenu(sessionId) {
        // Close all other menus
        document.querySelectorAll('.session-context-menu').forEach(el => {
            if (el.id !== `session-menu-${sessionId}`) {
                el.style.display = 'none';
                resetDeleteButtons(el);
            }
        });

        const menu = document.getElementById(`session-menu-${sessionId}`);
        if (menu.style.display === 'block') {
            menu.style.display = 'none';
            resetDeleteButtons(menu);
        } else {
            menu.style.display = 'block';
        }
    }

    function resetDeleteButtons(menu) {
        if (!menu) return;
        const btn = menu.querySelector('.delete-btn');
        if (btn) {
            btn.textContent = 'Delete';
            btn.style.background = '';
            btn.style.color = '';
        }
    }

    // Close menus when clicking elsewhere
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.session-menu-trigger')) {
            document.querySelectorAll('.session-context-menu').forEach(el => {
                el.style.display = 'none';
                resetDeleteButtons(el);
            });
        }
    });

    async function createNewSession() {
        try {
            console.log("[DEBUG] Requesting new session...");
            const data = await authFetch('/sessions/new', { method: 'POST' });
            console.log("[DEBUG] New session created:", data);
            // Auto switch to it
            activeSessionId = data.id;

            // Clear UI
            messagesContainer.innerHTML = `
                <div class="message system">
                    <div class="avatar">AG</div>
                    <div class="content">
                        ${(window.t ? window.t('type_message') : 'Hello')} ${currentUser ? currentUser.username : ''}! ${(window.t ? window.t('new_session_welcome') : 'Ready for a new task.')}
                    </div>
                </div>`;
            // Refresh list
            await loadSessions();
        } catch (e) {
            console.error(e);
        }
    }

    async function deleteSession(sid) {
        try {
            await authFetch(`/sessions/${sid}`, { method: 'DELETE' });

            // If we deleted the active session, clear the screen
            if (sid === activeSessionId) {
                messagesContainer.innerHTML = '';
                activeSessionId = null;
                messagesContainer.innerHTML = `
                <div class="message system">
                    <div class="avatar">AG</div>
                    <div class="content">
                        ${window.t ? window.t('session_deleted') : 'Session deleted. Please create or select a session.'}
                    </div>
                </div>`;
            }

            loadSessions();
        } catch (e) {
            console.error(e);
            if (!confirm(window.t ? window.t('delete_confirm') : 'Are you sure you want to delete this session?')) return;
            alert("Failed to delete session: " + e.message);
        }
    }


    async function switchSession(sid) {
        try {
            const data = await authFetch(`/sessions/${sid}/load`, { method: 'POST' });
            if (!data) return;
            activeSessionId = sid;

            // Clear UI
            if (messagesContainer) {
                messagesContainer.innerHTML = '';
            }

            // Render History
            if (data.history && messagesContainer) {
                data.history.forEach(msg => {
                    renderHistoryMessage(msg);
                });
            }

            // Refresh list to highlight active
            loadSessions();

        } catch (e) {
            console.error(e);
        }
    }

    function renderHistoryMessage(msg) {
        if (!messagesContainer) return;

        if (msg.role === 'user') {
            addMessage('user', msg.content);

            // [中文注解] 检查这条用户消息是否是对上面那个"互动提问"的回答
            // Check if this user message answers a pending interaction block
            // 1. 找到页面上最后一个"互动提问"块 (Find the last interaction block)
            const blocks = messagesContainer.querySelectorAll('.interaction-block');
            if (blocks.length > 0) {
                const lastBlock = blocks[blocks.length - 1];

                // 2. 检查这个块里的按钮是不是还没被禁用 (即处于"未回答"状态)
                // Check if it has active buttons (meaning it's unanswered)
                const buttons = lastBlock.querySelectorAll('button:not([disabled])');
                if (buttons.length > 0) {
                    // 3. 如果是跟在提问后面的用户消息，我们就认为它是回答，把提问块设为"已完成"(灰色)
                    // Mark the block as completed using the user's content
                    completeInteractionBlock(lastBlock, msg.content);
                }
            }

        } else if (msg.role === 'assistant') {
            const container = addAssistantMessagePlaceholder();

            // Render Thinking
            if (msg.reasoning_content) {
                const th = createThinkingBlock(container);
                th.querySelector('.thinking-content').textContent = msg.reasoning_content;
                // [English] Convert Markdown text to HTML using the library
                // [中文说明] 使用该库将 Markdown 文本转换为 HTML
                try {
                    th.querySelector('.thinking-content').innerHTML = marked.parse(msg.reasoning_content);
                } catch (e) { }
                th.classList.add('collapsed');
            }

            // Render Tools
            if (msg.tool_calls) {
                msg.tool_calls.forEach(tc => {
                    // Check for ask_followup_question
                    if (tc.function.name === 'ask_followup_question') {
                        try {
                            const args = JSON.parse(tc.function.arguments);
                            createInteractionBlock(container, {
                                question: args.question,
                                options: args.follow_up, // Note: Python sends 'follow_up', args needs to match
                                id: tc.id // Pass ID to link with answer later
                            });
                        } catch (e) {
                            console.error("Failed to parse interaction in history", e);
                            createToolBlock(container, {
                                id: tc.id,
                                name: tc.function.name,
                                args: tc.function.arguments
                            });
                        }
                    } else {
                        // Standard Tool
                        createToolBlock(container, {
                            id: tc.id,
                            name: tc.function.name,
                            args: tc.function.arguments
                        });
                    }
                });
            }

            // Render Content
            if (msg.content) {
                const contentDiv = document.createElement('div');
                contentDiv.className = 'text-content markdown-body';
                // [English] Convert Markdown text to HTML using the library
                // [中文说明] 使用该库将 Markdown 文本转换为 HTML
                contentDiv.innerHTML = marked.parse(msg.content);
                container.appendChild(contentDiv);
            }
        } else if (msg.role === 'tool') {
            // [中文注解] 忽略掉系统内部产生的占位符消息
            // 系统处于"等待用户输入"状态时，会产生一条工具消息，我们不能因为这条消息就把按钮禁用了！
            // IGNORE placeholder output so buttons stay active!
            if (msg.content && msg.content.includes("[WAITING FOR USER INPUT]")) {
                console.log("Skipping placeholder for", msg.tool_call_id);
                return; // 直接返回，不做任何处理 -> 按钮保持绿色(可点)
            }

            const toolBlock = messagesContainer.querySelector(`.tool-block[data-id="${msg.tool_call_id}"]`);
            if (toolBlock) {
                completeToolBlock(toolBlock, msg.content);
            }
            // Also check for interaction block
            const interactionBlock = messagesContainer.querySelector(`.interaction-block[data-id="${msg.tool_call_id}"]`);
            if (interactionBlock) {
                completeInteractionBlock(interactionBlock, msg.content);
            }
        }
    }

    // Function: sendMessage / 发送消息主函数
    // The most complex part! It handles user input and server streaming.
    // 最复杂的部分！它处理用户输入和接收服务器的流式响应。
    async function sendMessage() {
        const text = userInput.value.trim(); // Get text and remove spaces / 获取文本并去除首尾空格
        if (!text) return; // If empty, do nothing / 如果是空的，什么都不做

        // 1. Add User Message to UI / 1. 把用户的消息添加到界面上
        addMessage('user', text);
        userInput.value = ''; // Clear input box / 清空输入框
        userInput.style.height = 'auto'; // Reset height / 重置高度
        sendBtn.disabled = true; // Disable button to prevent double-click / 禁用按钮防止重复点击

        // Reset State for new turn
        // 重置状态变量，为新的一轮对话做准备
        stepCount = 0;
        currentStepEl = null;
        activeThinking = null;
        activeContent = null;
        activeTool = null;

        // 2. Create Assistant Message Placeholder / 2. 创建一个"机器人正在输入"的占位符
        const assistantMsgBody = addAssistantMessagePlaceholder();

        try {
            // 3. Start SSE Streaming / 3. 开始 SSE 流式请求
            // We use native 'fetch' here instead of 'authFetch' to handle the stream better.
            // 用原生 fetch 来处理流数据。
            const headers = { 'Content-Type': 'application/json' };
            if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`; // Attach Token / 带上 Token

            const response = await fetch('/chat', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ message: text, session_id: activeSessionId })
            });

            if (response.status === 401) {
                logout();
                throw new Error("Unauthorized");
            }

            // Get a reader to read the stream bit by bit / 获取读取器，一点一点读取数据
            const reader = response.body.getReader();
            const decoder = new TextDecoder(); // To decode binary data to text / 用于将二进制数据解码为文本

            // Loop to read the stream / 循环读取流
            while (true) {
                const { value, done } = await reader.read(); // Read next chunk / 读取下一块数据
                if (done) break; // If finished, stop / 如果读完了，跳出循环

                // Decode incoming bytes to text / 将收到的字节解码为文本
                const chunk = decoder.decode(value, { stream: true });
                // One chunk might contain multiple "data: {}" lines
                // 一块数据可能包含多行 "data: {}"
                const lines = chunk.split('\n\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            // Extract JSON / 提取 JSON
                            const jsonStr = line.substring(6);
                            const event = JSON.parse(jsonStr);
                            // Handle the event (Update UI) / 处理事件（更新界面）
                            handleEvent(event, assistantMsgBody);
                        } catch (e) {
                            console.error("Error parsing SSE:", e);
                        }
                    }
                }
            }
        } catch (err) {
            console.error(err);
            // Show error message in chat / 在聊天中显示错误信息
            const errDiv = document.createElement('div');
            errDiv.className = 'text-content';
            errDiv.style.color = '#ff5c5c';
            errDiv.textContent = 'Error: ' + err.message;
            assistantMsgBody.appendChild(errDiv);
        } finally {
            sendBtn.disabled = false; // Re-enable send button / 重新启用发送按钮
        }
    }

    // State trackers for the current stream
    let stepCount = 0;
    let currentStepEl = null;
    let activeThinking = null;
    let activeContent = null;
    let activeTool = null;

    // Function: handleEvent / 处理 SSE 事件
    // This function decides what to draw based on the event type.
    // 这个函数根据事件类型决定在屏幕上画什么。
    function handleEvent(event, container) {
        const type = event.type;    // e.g. 'check_start', 'thinking_delta', 'content_delta'
        const content = event.content; // The actual text or data / 实际的文本数据

        // Scroll to bottom so we see new text
        // 滚动到底部，以便看到新出来的字
        setTimeout(() => {
            messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
        }, 50);

        // [Event Type 1] New Step Started / 新步骤开始了
        if (type === 'stream_start') {
            stepCount++;
            // Create a numbered step indicator (e.g. "1", "2")
            // 创建一个带数字的步骤指示器
            currentStepEl = createStepBlock(container, stepCount);
            // Reset active blocks for this new step / 重置当前步骤的活动块
            activeThinking = null;
            activeContent = null;
            activeTool = null;
            return;
        }

        // If no step yet (first event), create one
        if (!currentStepEl && type !== 'finished' && type !== 'error') {
            stepCount++;
            currentStepEl = createStepBlock(container, stepCount);
        }

        const targetContainer = currentStepEl ? currentStepEl.querySelector('.step-content') : container;

        // [Event Type 2] Thinking (Reasoning) / 思考过程
        if (type === 'thinking_delta') {
            activeContent = null;
            // If we don't have a thinking block yet, create one
            // 如果还没有思考块，创建一个
            if (!activeThinking) {
                activeThinking = createThinkingBlock(targetContainer);
            }
            // Append new text to the thinking block
            // 把新收到的字追加到思考块里
            const contentEl = activeThinking.querySelector('.thinking-content');
            if (!contentEl.dataset.raw) contentEl.dataset.raw = "";
            contentEl.dataset.raw += content;
            try {
                // [English] Convert raw thinking text to HTML
                // [中文说明] 将思考过程的文本转换为 HTML
                contentEl.innerHTML = marked.parse(contentEl.dataset.raw);
            } catch (e) {
                contentEl.textContent = contentEl.dataset.raw;
            }
        }

        // [Event Type 3] Final Answer Content / 最终回答内容
        else if (type === 'content_delta') {
            activeThinking = null;
            if (!activeContent) {
                activeContent = document.createElement('div');
                activeContent.className = 'text-content markdown-body';
                targetContainer.appendChild(activeContent);
            }
            if (!activeContent.dataset.raw) activeContent.dataset.raw = "";
            activeContent.dataset.raw += content;
            try {
                // [English] Convert raw message text to HTML
                // [中文说明] 将原始消息文本转换为 HTML
                activeContent.innerHTML = marked.parse(activeContent.dataset.raw);
            } catch (e) {
                activeContent.textContent = activeContent.dataset.raw;
            }
        }
        else if (type === 'assistant') { // Fallback for simple content
            activeThinking = null;
            if (!activeContent) {
                activeContent = document.createElement('div');
                activeContent.className = 'text-content markdown-body';
                targetContainer.appendChild(activeContent);
            }
            // [English] Convert full Markdown text
            // [中文说明] 转换完整的 Markdown 文本
            activeContent.innerHTML = marked.parse(content);
        }

        // --- Tools ---
        else if (type === 'tool_call') {
            activeThinking = null;
            activeContent = null;
            activeTool = createToolBlock(targetContainer, content);
        }
        else if (type === 'tool_output') {
            if (activeTool && activeTool.dataset.id === content.id) {
                completeToolBlock(activeTool, content.output);
                activeTool = null;
            } else {
                const tool = container.querySelector(`.tool-block[data-id="${content.id}"]`);
                if (tool) completeToolBlock(tool, content.output);
            }
        }

        // --- Interrupt (Ask User) ---
        else if (type === 'interrupt') {
            // content = { "action": "ask_user", "question": "...", "options": [...] }
            createInteractionBlock(container, content);
        }

        // --- Finished ---
        else if (type === 'finished') {
            stepCount = 0; // Reset for next turn
            currentStepEl = null;
            activeThinking = null;
            activeContent = null;
            activeTool = null;
        }
    }

    // Helpers
    function completeToolBlock(block, output) {
        const outputEl = block.querySelector('.tool-output');
        outputEl.innerText = output;
        outputEl.classList.remove('hidden');
        block.querySelector('.status').textContent = 'Completed';
        block.querySelector('.status').style.color = '#3dd68c';
        block.classList.add('completed');
    }

    function addMessage(role, text) {
        const template = document.getElementById(`msg-template-${role}`);
        const clone = template.content.cloneNode(true);
        const div = clone.querySelector('.message');
        // Verify online status (mock)
        if (window.t) {
            document.querySelector('.user-status').innerHTML = window.t('is_active');
        }
        if (role === 'user') {
            div.querySelector('.content').textContent = text;
            div.querySelector('.user .avatar').textContent = window.t ? window.t('user_profile') : 'You'; // Use 'My Profile' or just 'You' key? 'You' isn't in dict. Let's use 'User' or add 'you' to dict.
            // Actually let's use username or 'You'. Dictionary doesn't have 'you'. 
            // Let's safe fallback.
            div.querySelector('.user .avatar').textContent = 'You';
            if (window.t && window.translations[window.currentLanguage].you) {
                div.querySelector('.user .avatar').textContent = window.t('you');
            }
        }
        else {
            // Assistant
            div.innerHTML = marked.parse(text);
            div.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }
        messagesContainer.appendChild(div);
        messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
    }

    function addAssistantMessagePlaceholder() {
        const template = document.getElementById('msg-template-assistant');
        const clone = template.content.cloneNode(true);
        const div = clone.querySelector('.message');
        const body = div.querySelector('.message-body');
        messagesContainer.appendChild(div);
        return body;
    }

    function createStepBlock(container, stepNum) {
        const div = document.createElement('div');
        div.className = 'execution-step';
        div.innerHTML = `
            <div class="step-indicator">
                <div class="step-number">${stepNum}</div>
                <div class="step-line"></div>
            </div>
            <div class="step-content"></div>
        `;
        container.appendChild(div);
        return div;
    }

    function createThinkingBlock(container) {
        const template = document.getElementById('thinking-template');
        const clone = template.content.cloneNode(true);
        const block = clone.querySelector('.thinking-block');
        block.querySelector('.thinking-header').addEventListener('click', () => {
            block.classList.toggle('collapsed');
        });
        block.classList.remove('collapsed');
        container.appendChild(block);
        return block;
    }

    function createToolBlock(container, data) {
        const template = document.getElementById('tool-call-template');
        const clone = template.content.cloneNode(true);
        const block = clone.querySelector('.tool-block');
        block.dataset.id = data.id;
        block.querySelector('.tool-name').textContent = data.name;
        block.querySelector('.tool-args').textContent = data.args;
        container.appendChild(block);
        return block;
    }

    function createInteractionBlock(container, data) {
        console.log("Creating Interaction Block:", data);
        const div = document.createElement('div');
        div.className = 'interaction-block';
        if (data.id) div.dataset.id = data.id; // Set ID for history tracking

        div.style.marginTop = '16px';
        div.style.padding = '16px';
        div.style.background = 'rgba(238, 187, 77, 0.1)'; // Warning color tint
        div.style.border = '1px solid var(--warning)';
        div.style.borderRadius = '8px';
        div.style.width = '100%';
        div.style.boxSizing = 'border-box';

        const questionEl = document.createElement('div');
        questionEl.className = 'markdown-body';
        questionEl.style.fontWeight = 'bold';
        questionEl.style.marginBottom = '12px';
        questionEl.style.color = 'var(--text-main)';

        try {
            // [English] Convert question text to HTML (it might contain bold/lists)
            // [中文说明] 将问题文本转换为 HTML (因为可能包含加粗或列表)
            questionEl.innerHTML = "❓ " + marked.parse(data.question);
        } catch (e) {
            questionEl.textContent = "❓ " + data.question;
        }
        div.appendChild(questionEl);

        const optionsDiv = document.createElement('div');
        optionsDiv.style.display = 'flex';
        optionsDiv.style.flexDirection = 'column';
        optionsDiv.style.gap = '8px';
        optionsDiv.style.width = '100%'; // Force full width

        data.options.forEach(opt => {
            const btn = document.createElement('button');
            btn.textContent = opt.text;
            if (opt.mode) btn.textContent += ` (Switch to ${opt.mode})`;

            btn.style.width = '100%'; // Force full width
            btn.style.padding = '10px';
            btn.style.background = 'rgba(255,255,255,0.05)';
            btn.style.border = '1px solid var(--glass-border)';
            btn.style.borderRadius = '6px';
            btn.style.color = 'var(--text-main)';
            btn.style.cursor = 'pointer';
            btn.style.textAlign = 'left';
            btn.style.whiteSpace = 'normal'; // Allow text wrap
            btn.style.lineHeight = '1.4';
            btn.style.minWidth = '200px';

            btn.onmouseover = () => { if (!btn.disabled) btn.style.background = 'rgba(255,255,255,0.1)'; }
            btn.onmouseout = () => { if (!btn.disabled) btn.style.background = 'rgba(255,255,255,0.05)'; }

            btn.onclick = () => {
                const userInput = document.getElementById('userInput');
                userInput.value = opt.text;
                sendMessage();

                const allBtns = optionsDiv.querySelectorAll('button');
                allBtns.forEach(b => {
                    b.disabled = true;
                    b.style.opacity = '0.5';
                });
            };
            optionsDiv.appendChild(btn);
        });

        div.appendChild(optionsDiv);
        container.appendChild(div);

        setTimeout(() => {
            container.closest('.messages').scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
        }, 100);
    }

    function completeInteractionBlock(block, answer) {
        // [中文注解] 终极防线 (Ultimate Guard)
        // 如果传进来的"答案"竟然包含了那个占位符，说明系统搞错了，绝对不能把按钮禁用！
        // ULTIMATE GUARD: If answer comes from the placeholder tool output, IGNORE IT.
        if (answer && answer.includes("[WAITING FOR USER INPUT]")) {
            return; // 也不做任何处理
        }

        // [中文注解] 禁用所有按钮 (变灰)
        // Disable all buttons
        const buttons = block.querySelectorAll('button');
        let matched = false;

        buttons.forEach(btn => {
            btn.disabled = true;
            btn.style.cursor = 'default';
            // Check if this button text corresponds to the answer
            // The answer might include "USER ANSWER: " prefix if from ToolResult output, 
            // or just the text if found in logic. 
            // Usually tool result output is "USER ANSWER: ...".

            const rawText = btn.textContent;
            // Simple robust check: if answer contains the button text
            if (answer.includes(rawText)) {
                btn.style.background = 'rgba(61, 214, 140, 0.2)'; // Success color tint
                btn.style.border = '1px solid var(--success)';
                btn.style.opacity = '1';
                matched = true;
            } else {
                btn.style.opacity = '0.3';
                btn.style.background = 'transparent';
                btn.style.border = '1px solid transparent';
            }
        });

        if (!matched) {
            // Maybe custom input? Add a small footer
            const footer = document.createElement('div');
            footer.style.marginTop = '8px';
            footer.style.fontSize = '0.9em';
            footer.style.color = 'var(--text-dim)';
            footer.textContent = `${window.t ? window.t('custom_answer') : 'Custom Answer'}: ${answer.replace('USER ANSWER: ', '')}`;
            block.appendChild(footer);
        }
    }
});
