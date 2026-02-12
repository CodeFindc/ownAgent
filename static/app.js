document.addEventListener('DOMContentLoaded', () => {
    // [DOM Element Selection / 获取页面元素]
    // These variables store references to HTML elements so we can manipulate them later.
    // 这些变量存储了对 HTML 元素的引用，以便我们稍后操作它们。
    const messagesContainer = document.getElementById('messages'); // The chat history area / 聊天记录区域
    const userInput = document.getElementById('userInput');        // The input box / 输入框
    const sendBtn = document.getElementById('sendBtn');            // The send button / 发送按钮
    const sessionListEl = document.getElementById('sessionList');  // The sidebar history list / 侧边栏历史列表
    const newChatBtn = document.getElementById('newChatBtn');      // "New Chat" button / "新建聊天"按钮

    // Auth UI Elements / 认证相关的界面元素
    const loginModal = document.getElementById('loginModal');       // The login popup / 登录弹窗
    const loginForm = document.getElementById('loginForm');         // The login form / 登录表单
    const loginError = document.getElementById('loginError');       // Where to show login errors / 显示登录错误的地方
    const userProfileEl = document.getElementById('userProfile');   // User profile section (bottom left) / 用户资料区域（左下角）
    const userNameDisplay = document.getElementById('userNameDisplay'); // Where to show username / 显示用户名的地方
    const logoutBtn = document.getElementById('logoutBtn');         // Logout text link / 注销链接

    // State / 状态变量
    // accessToken: The key to prove we are logged in (stored in browser)
    // accessToken: 证明我们已登录的密钥（存储在浏览器中）
    let accessToken = localStorage.getItem('access_token');
    let currentUser = null;     // Current logged-in user info / 当前登录的用户信息
    let activeSessionId = null; // Current chat session ID / 当前聊天会话的 ID

    // --- Authentication Logic / 认证逻辑 ---

    // 1. Check Auth on Startup / 启动时检查认证状态
    // If we have a token, check if it's still valid. If not, show login.
    // 如果我们有 token，检查它是否有效。如果无效，显示登录框。
    if (accessToken) {
        checkAuthStatus();
    } else {
        showLogin();
    }

    // Function: checkAuthStatus / 检查认证状态函数
    // Async function to fetch user details from server.
    // 异步函数：从服务器获取用户详情
    async function checkAuthStatus() {
        try {
            // Send a request to '/auth/users/me' using our helper function
            // 使用我们的辅助函数向 '/auth/users/me' 发送请求
            const user = await authFetch('/auth/users/me');
            currentUser = user;
            updateUIForLoggedIn(user); // Update screen to show user is logged in / 更新屏幕显示已登录状态
            await loadSessions();      // Load chat history list / 加载聊天历史列表
        } catch (e) {
            console.error("Auth check failed:", e);
            logout(); // If check fails, force logout / 如果检查失败，强制注销
        }
    }

    // 2. Login Event Listener / 登录事件监听器
    // When user submits the login form...
    // 当用户提交登录表单时...
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault(); // Stop page from refreshing / 阻止页面刷新
        const formData = new FormData(loginForm); // Collect input data / 收集输入数据

        try {
            // Send username/password to server to get a token
            // 发送用户名/密码给服务器以获取 token
            const res = await fetch('/auth/token', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                // If login fails (e.g. wrong password), show error
                // 如果登录失败（如密码错误），显示错误信息
                const err = await res.json();
                throw new Error(err.detail || 'Login failed');
            }

            // Success! We got the token.
            // 成功！我们拿到了 token。
            const data = await res.json();
            accessToken = data.access_token;
            localStorage.setItem('access_token', accessToken); // Save it / 保存它

            // Fetch User Details to confirm everything is OK
            // 获取用户详情以确认一切正常
            await checkAuthStatus();

            hideLogin(); // Close the modal / 关闭弹窗
        } catch (e) {
            loginError.textContent = e.message; // Show error on screen / 在屏幕上显示错误
        }
    });

    // 3. Logout / 注销
    logoutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        logout(); // Call logout function / 调用注销函数
    });

    // Function: logout / 注销函数
    // Clears all user data and resets the state.
    // 清除所有用户数据并重置状态。
    function logout() {
        accessToken = null;
        currentUser = null;
        localStorage.removeItem('access_token'); // Delete token from storage / 从存储中删除 token
        showLogin(); // Show login screen again / 再次显示登录界面
        userProfileEl.style.display = 'none'; // Hide user profile / 隐藏左下角用户资料
        messagesContainer.innerHTML = ''; // Clear chat history / 清空聊天记录
        sessionListEl.innerHTML = '';     // Clear session list / 清空会话列表
    }

    function showLogin() {
        loginModal.style.display = 'flex';
        loginForm.reset();
        loginError.textContent = '';
    }

    function hideLogin() {
        loginModal.style.display = 'none';
    }

    function updateUIForLoggedIn(user) {
        userProfileEl.style.display = 'block';
        userNameDisplay.textContent = user.username + (user.role === 'admin' ? ' (Admin)' : '');
        // Restore Welcome
        if (messagesContainer.children.length <= 1) {
            messagesContainer.innerHTML = `
                <div class="message system">
                    <div class="avatar">AG</div>
                    <div class="content">
                        Hello ${user.username}! I am your Agent. How can I help you today?
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
    userInput.addEventListener('keydown', (e) => {
        // If Enter is pressed WITHOUT Shift (Send)
        // 如果按下了回车，且没有按 Shift（ Shift+Enter 是换行）
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Don't add a new line / 不要在输入框里换行
            sendMessage(); // Send the message / 发送消息
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    newChatBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        await createNewSession();
    });

    async function loadSessions() {
        try {
            const data = await authFetch('/sessions');
            // Check if array or object from wrapper
            // authFetch returns json object if json content-type

            sessionListEl.innerHTML = '';
            if (data && data.sessions) {
                if (data.current_session_id) activeSessionId = data.current_session_id;
                data.sessions.forEach(sess => {
                    const a = document.createElement('a');
                    a.href = '#';
                    a.dataset.id = sess.id;
                    const date = new Date(sess.timestamp * 1000);
                    const timeStr = date.toLocaleString();

                    a.innerHTML = `<div style="font-weight:500">Session ${sess.id.substring(9)}</div><div style="font-size:0.7em; color:var(--text-dim)">${timeStr}</div>`;

                    if (sess.id === data.current_session_id) {
                        a.classList.add('active');
                    }

                    a.addEventListener('click', (e) => {
                        e.preventDefault();
                        switchSession(sess.id);
                    });

                    sessionListEl.appendChild(a);
                });
            }
        } catch (e) {
            console.error("Failed to load sessions", e);
        }
    }

    async function createNewSession() {
        try {
            await authFetch('/sessions/new', { method: 'POST' });
            // Clear UI
            messagesContainer.innerHTML = `
                <div class="message system">
                    <div class="avatar">AG</div>
                    <div class="content">
                        Hello ${currentUser ? currentUser.username : ''}! Ready for a new task.
                    </div>
                </div>`;
            // Refresh list
            loadSessions();
        } catch (e) {
            console.error(e);
        }
    }

    async function switchSession(sid) {
        try {
            const data = await authFetch(`/sessions/${sid}/load`, { method: 'POST' });
            if (!data) return;
            activeSessionId = sid;

            // Clear UI
            messagesContainer.innerHTML = '';

            // Render History
            if (data.history) {
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
        if (role === 'user') {
            div.querySelector('.content').textContent = text;
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
            footer.textContent = `Custom Answer: ${answer.replace('USER ANSWER: ', '')}`;
            block.appendChild(footer);
        }
    }
});
