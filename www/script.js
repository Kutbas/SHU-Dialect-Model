// 配置
const API_BASE_URL = 'http://192.168.71.45:60310';

// 全局变量
let currentSessionId = null;
let currentModel = null;
let sessions = [];
let models = [];
let selectedModel = null;
let eventSource = null;
const activeStreams = {}; // 用于保存后台正在生成的流状态
const sessionDrafts = {}; // 用于保存每个会话的草稿箱
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;


// DOM 元素
const elements = {
    newChatBtn: document.getElementById('newChatBtn'),
    welcomeNewChatBtn: document.getElementById('welcomeNewChatBtn'),
    sessionList: document.getElementById('sessionList'),
    welcomeScreen: document.getElementById('welcomeScreen'),
    chatInterface: document.getElementById('chatInterface'),
    messagesContainer: document.getElementById('messagesContainer'),
    messageInput: document.getElementById('messageInput'),
    sendBtn: document.getElementById('sendBtn'),
    charCount: document.getElementById('charCount'),
    modelModal: document.getElementById('modelModal'),
    modelGrid: document.getElementById('modelGrid'),
    closeModal: document.getElementById('closeModal'),
    cancelBtn: document.getElementById('cancelBtn'),
    confirmBtn: document.getElementById('confirmBtn'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    recordBtn: document.getElementById('recordBtn')
};

// 初始化应用
document.addEventListener('DOMContentLoaded', function () {
    initializeApp();
    setupEventListeners();
});

// 初始化应用
function initializeApp() {
    // 配置 marked 用于 Markdown 渲染
    marked.setOptions({
        highlight: function (code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (err) {
                    console.error('Highlight error:', err);
                }
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true,           // 将换行符转换为 <br>
        gfm: true,             // 启用 GitHub Flavored Markdown
        tables: true,          // 启用表格支持
        pedantic: false,       // 不启用严格模式
        sanitize: false,       // 不清理HTML
        smartLists: true,      // 启用智能列表
        smartypants: true,     // 启用智能标点
        xhtml: false,          // 不生成XHTML
        renderer: new marked.Renderer()
    });

    // 重写代码块渲染器，添加包装器
    const renderer = new marked.Renderer();
    const originalCodeRenderer = renderer.code;
    renderer.code = function (code, language, isEscaped) {
        const langClass = language ? `language-${language}` : '';
        const highlightedCode = originalCodeRenderer.call(this, code, language, isEscaped);

        // 包装代码块，添加复制按钮容器
        return `
        <div class="code-block-wrapper">
            ${highlightedCode}
        </div>
    `;
    };

    marked.setOptions({ renderer });

    // 加载会话列表和模型列表
    loadSessions();
    loadModels();
}

// 设置事件监听器
function setupEventListeners() {
    // 新建对话按钮
    elements.newChatBtn.addEventListener('click', showModelModal);
    elements.welcomeNewChatBtn.addEventListener('click', showModelModal);

    // 消息输入
    elements.messageInput.addEventListener('input', updateCharCount);
    elements.messageInput.addEventListener('keydown', handleKeyDown);

    // 发送按钮
    elements.sendBtn.addEventListener('click', sendMessage);
    // 录音按钮点击事件
    if (elements.recordBtn) {
        elements.recordBtn.addEventListener('click', toggleRecording);
    }

    // 模型选择弹窗
    elements.closeModal.addEventListener('click', hideModelModal);
    elements.cancelBtn.addEventListener('click', hideModelModal);
    elements.confirmBtn.addEventListener('click', createNewSession);

    // 点击弹窗外部关闭
    elements.modelModal.addEventListener('click', function (e) {
        if (e.target === elements.modelModal) {
            hideModelModal();
        }
    });

    // 滚动同步：消息区域滚动时同步会话列表
    elements.messagesContainer.addEventListener('scroll', syncSessionListScroll);
}

// 滚动同步函数
function syncSessionListScroll() {
    const messagesScrollTop = elements.messagesContainer.scrollTop;
    const messagesScrollHeight = elements.messagesContainer.scrollHeight;
    const messagesClientHeight = elements.messagesContainer.clientHeight;

    const sessionList = document.querySelector('.session-list');
    if (sessionList) {
        const sessionScrollHeight = sessionList.scrollHeight;
        const sessionClientHeight = sessionList.clientHeight;

        // 只有当两个容器都有滚动内容时才进行同步
        if (messagesScrollHeight > messagesClientHeight && sessionScrollHeight > sessionClientHeight) {
            // 计算会话列表应该滚动到的位置
            const messagesScrollRatio = messagesScrollTop / (messagesScrollHeight - messagesClientHeight);
            const sessionScrollTop = messagesScrollRatio * (sessionScrollHeight - sessionClientHeight);

            // 使用requestAnimationFrame确保平滑滚动
            requestAnimationFrame(() => {
                sessionList.scrollTop = sessionScrollTop;
            });
        }
    }
}

// 自动滚动到消息区域底部
function scrollToBottom(isInstant = false) {
    // 使用 setTimeout 的 'auto' 模式给浏览器时间计算 DOM 的实际高度
    setTimeout(() => {
        if (elements.messagesContainer) {
            // 使用现代的标准 scrollTo API，抛弃修改 CSS 的 Hack 做法
            elements.messagesContainer.scrollTo({
                top: elements.messagesContainer.scrollHeight,
                behavior: isInstant ? 'auto' : 'smooth'
            });
        }
    });
}



// API 调用函数

// 获取会话列表
async function loadSessions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sessions`);
        const data = await response.json();

        if (data.success) {
            sessions = data.data || [];
            renderSessionList();
        } else {
            showError('加载会话列表失败: ' + data.message);
        }
    } catch (error) {
        console.error('加载会话列表错误:', error);
        showError('网络错误，请检查服务器连接');
    }
}

// 获取模型列表
async function loadModels() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/models`);
        const data = await response.json();

        if (data.success) {
            models = data.data || [];
            renderModelGrid();
        } else {
            showError('加载模型列表失败: ' + data.message);
        }
    } catch (error) {
        console.error('加载模型列表错误:', error);
        showError('网络错误，请检查服务器连接');
    }
}

// 创建新会话
async function createNewSession() {
    if (!selectedModel) {
        showError('请选择一个模型');
        return;
    }

    showLoading(true);

    try {
        const response = await fetch(`${API_BASE_URL}/api/session`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: selectedModel
            })
        });

        const data = await response.json();

        if (data.success) {
            // 保存旧会话草稿
            if (currentSessionId) {
                sessionDrafts[currentSessionId] = elements.messageInput.value;
            }

            currentSessionId = data.data.session_id;
            currentModel = data.data.model;

            // 新会话输入框必然为空，并重置字数统计
            elements.messageInput.value = '';
            updateCharCount();

            // 重新加载会话列表
            await loadSessions();

            // 切换到聊天界面
            switchToChatInterface();

            // 关闭模型选择弹窗
            hideModelModal();

            // 如果有开场白，直接渲染开场白
            const history = await loadSessionHistory(currentSessionId);
            renderChatHistory(history);

            // 移除创建成功提示，避免干扰用户体验
            // showSuccess('新会话创建成功！');
        } else {
            showError('创建会话失败: ' + data.message);
        }
    } catch (error) {
        console.error('创建会话错误:', error);
        showError('网络错误，请检查服务器连接');
    } finally {
        showLoading(false);
    }
}

// 发送消息
async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();

    if (!message) {
        showError('请输入消息内容');
        return;
    }

    if (!currentSessionId) {
        showError('请先选择或创建会话');
        return;
    }

    // 锁定发送时的目标会话 ID
    const targetSessionId = currentSessionId;

    elements.sendBtn.disabled = true;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => { controller.abort(); }, 90000);

        // 1. 添加用户消息气泡到页面
        const userMessageId = addMessageToChat('user', message);

        // 2. 准确清空输入框和对应草稿（【千万注意】：这里绝对不能是 messagesContainer）
        messageInput.value = '';
        if (typeof sessionDrafts !== 'undefined') {
            sessionDrafts[targetSessionId] = '';
        }
        updateCharCount();

        // 3. 紧接着添加 AI “思考中”气泡
        const aiMessageId = addMessageToChat('assistant', '', true);

        // 4. 【关键修复】：气泡全部塞入 DOM 后，触发沉底滚动（内部自带 50ms 等待）
        scrollToBottom(true);

        // 5. 登记后台流状态
        activeStreams[targetSessionId] = { messageId: aiMessageId, fullContent: '', displayedContent: '', isFinished: false };

        const isFullResponseModel = currentModel && currentModel.includes('小沪');
        const endpoint = isFullResponseModel ? '/api/message' : '/api/message/async';

        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: targetSessionId, message: message }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        if (isFullResponseModel) {
            // 全量响应逻辑
            const data = await response.json();
            if (data.success) {
                if (currentSessionId === targetSessionId) {
                    // 先把文本渲染上去
                    updateMessageContent(aiMessageId, data.data.response);

                    // 如果后端传回了音频链接，直接挂载播放器！
                    if (data.data.audio_url) {
                        appendAudioPlayer(aiMessageId, data.data.audio_url);
                    }
                }
                delete activeStreams[targetSessionId];
            } else {
                if (currentSessionId === targetSessionId) showError('获取回复失败: ' + data.message);
                delete activeStreams[targetSessionId];
            }
        } else {
            // 原有的流式响应逻辑
            await processStreamResponse(response, aiMessageId, targetSessionId);
        }

    } catch (error) {
        console.error('发送消息错误:', error);

        // 发生错误时，仅清理当前会话的残留“思考中”气泡
        if (currentSessionId === targetSessionId) {
            const streamState = activeStreams[targetSessionId];
            if (streamState && streamState.messageId) {
                const aiMessage = document.getElementById(streamState.messageId);
                if (aiMessage) aiMessage.remove();
            }
        }
        delete activeStreams[targetSessionId];

    } finally {
        elements.sendBtn.disabled = false;
    }
}

// 处理流式响应（支持多会话后台生成）
async function processStreamResponse(response, messageId, sessionId) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8"); // 确保使用 utf-8 解码
    let buffer = '';
    let streamState = activeStreams[sessionId];
    if (!streamState) return;

    // 启动打字机定时器 (保持原逻辑不变)
    const typewriterInterval = setInterval(() => {
        const remaining = streamState.fullContent.length - streamState.displayedContent.length;
        if (remaining > 0) {
            const charsToType = Math.max(1, Math.ceil(remaining / 5));
            streamState.displayedContent += streamState.fullContent.substring(streamState.displayedContent.length, streamState.displayedContent.length + charsToType);
            if (currentSessionId === sessionId) {
                updateMessageContent(streamState.messageId, streamState.displayedContent);
            }
        } else if (streamState.isFinished) {
            clearInterval(typewriterInterval);
            if (currentSessionId === sessionId) {
                updateMessageContent(streamState.messageId, streamState.fullContent);
            }
            delete activeStreams[sessionId];
        }
    }, 25);

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            let lineEnd;

            while ((lineEnd = buffer.indexOf('\n')) !== -1) {
                const line = buffer.substring(0, lineEnd).trim();
                buffer = buffer.substring(lineEnd + 1);

                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        streamState.isFinished = true;
                        return;
                    }

                    try {
                        // Python 直接发过来的就是 JSON 标准字符串，比如: "你好，\n世界"
                        // 直接用 JSON.parse 就能完美还原真实字符和换行符，无需任何正则替换！
                        const parsedData = JSON.parse(data);
                        streamState.fullContent += parsedData;
                    } catch (error) {
                        console.error('解析流数据 JSON 错误:', error, '原始数据:', data);
                    }
                }
            }
        }
    } catch (error) {
        console.error('处理流式响应错误:', error);
        throw error;
    } finally {
        streamState.isFinished = true;
        reader.releaseLock();
    }
}

// 获取会话历史
async function loadSessionHistory(sessionId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/session/${sessionId}/history`);
        const data = await response.json();

        console.log('历史消息API响应:', data);

        if (data.success) {
            // 检查每条消息的时间戳字段
            if (data.data && data.data.length > 0) {
                data.data.forEach((message, index) => {
                    console.log(`消息${index}:`, message, '时间戳字段:', message.timestamp, '类型:', typeof message.timestamp);
                });
            }
            return data.data || [];
        } else {
            showError('加载历史消息失败: ' + data.message);
            return [];
        }
    } catch (error) {
        console.error('加载历史消息错误:', error);
        showError('网络错误，请检查服务器连接');
        return [];
    }
}

// 删除会话
async function deleteSession(sessionId) {
    if (!confirm('确定要删除这个会话吗？此操作不可撤销。')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/session/${sessionId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            // 清理废弃会话的草稿
            delete sessionDrafts[sessionId];

            // 重新加载会话列表
            await loadSessions();

            // 如果删除的是当前会话，切换到欢迎界面
            if (currentSessionId === sessionId) {
                switchToWelcomeInterface();
            }
        } else {
            showError('删除会话失败: ' + data.message);
        }
    } catch (error) {
        console.error('删除会话错误:', error);
        showError('网络错误，请检查服务器连接');
    }
}

// 界面渲染函数

// 渲染会话列表
function renderSessionList() {
    elements.sessionList.innerHTML = '';

    if (sessions.length === 0) {
        elements.sessionList.innerHTML = '<div class="no-sessions">暂无会话记录</div>';
        return;
    }

    sessions.forEach(session => {
        const sessionElement = document.createElement('div');
        sessionElement.className = `session-item ${currentSessionId === session.id ? 'active' : ''}`;
        sessionElement.innerHTML = `
            <div class="session-header">
                <div class="session-time">${formatTime(session.updated_at)}</div>
                <button class="session-delete" onclick="deleteSession('${session.id}')">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
            <div class="session-message">${escapeHtml(session.first_user_message || '新对话')}</div>
            <div class="session-model">${escapeHtml(session.model)}</div>
        `;

        sessionElement.addEventListener('click', (e) => {
            if (!e.target.closest('.session-delete')) {
                selectSession(session);
            }
        });

        elements.sessionList.appendChild(sessionElement);
    });
}

// 渲染模型网格
function renderModelGrid() {
    elements.modelGrid.innerHTML = '';

    if (models.length === 0) {
        elements.modelGrid.innerHTML = '<div class="no-models">暂无可用模型</div>';
        return;
    }

    models.forEach(model => {
        const modelElement = document.createElement('div');
        modelElement.className = 'model-item';
        modelElement.innerHTML = `
            <div class="model-name">${escapeHtml(model.name)}</div>
            <div class="model-desc">${escapeHtml(model.desc)}</div>
        `;

        modelElement.addEventListener('click', () => {
            // 取消之前的选择
            document.querySelectorAll('.model-item').forEach(item => {
                item.classList.remove('selected');
            });

            // 选择当前模型
            modelElement.classList.add('selected');
            selectedModel = model.name;
            elements.confirmBtn.disabled = false;
        });

        elements.modelGrid.appendChild(modelElement);
    });
}

// 选择会话
async function selectSession(session) {
    // 在切换到新会话前，先保存当前会话输入框里的草稿
    if (currentSessionId) {
        sessionDrafts[currentSessionId] = elements.messageInput.value;
    }

    currentSessionId = session.id;
    currentModel = session.model;

    // 恢复目标会话的草稿（如果没有则赋空值），并更新字数统计
    elements.messageInput.value = sessionDrafts[currentSessionId] || '';
    updateCharCount();

    // 更新会话列表高亮
    renderSessionList();
    // 切换到聊天界面
    switchToChatInterface();

    // 加载并渲染历史消息
    const history = await loadSessionHistory(session.id);
    renderChatHistory(history);

    // 【新增核心接管逻辑】：检查后台是否还有没打完的流
    const activeStream = activeStreams[session.id];
    if (activeStream && !activeStream.isFinished) {
        // 重新挂载具有相同 ID 的聊天气泡（传入 true 会自带“思考中...”动画）
        addMessageToChat('assistant', '', true, null, activeStream.messageId);

        // 只有当 displayedContent 有内容时（流式响应），才去填入进度。
        // 对于全量响应，此时是空字符串，跳过这一步，保留“思考中...”的动画
        if (activeStream.displayedContent) {
            updateMessageContent(activeStream.messageId, activeStream.displayedContent);
        }

        scrollToBottom(true);

    }


}
// 切换到聊天界面
function switchToChatInterface() {
    elements.welcomeScreen.style.display = 'none';
    elements.chatInterface.style.display = 'flex';
    elements.messagesContainer.innerHTML = '';
}

// 切换到欢迎界面
function switchToWelcomeInterface() {
    // 保存当前草稿
    if (currentSessionId) {
        sessionDrafts[currentSessionId] = elements.messageInput.value;
    }

    elements.welcomeScreen.style.display = 'flex';
    elements.chatInterface.style.display = 'none';
    currentSessionId = null;
    currentModel = null;
    renderSessionList();
}

// 渲染聊天历史
function renderChatHistory(history) {
    // 渲染前强制关闭滚动动画，防止页面闪烁
    elements.messagesContainer.style.scrollBehavior = 'auto';
    elements.messagesContainer.innerHTML = '';

    // 双重排序机制（修复同秒消息错乱）
    history.sort((a, b) => {
        if (a.timestamp !== b.timestamp) return a.timestamp - b.timestamp;
        if (a.role === 'user' && b.role === 'assistant') return -1;
        if (a.role === 'assistant' && b.role === 'user') return 1;
        return 0;
    });

    history.forEach(message => {
        // 【关键修改】：传入第6个参数 skipScroll = true，阻止单条消息渲染时反复触发滚动
        addMessageToChat(message.role, message.content, false, message.timestamp, null, true);
    });

    // 所有历史消息渲染完后，触发一次“瞬间”滚动到底部
    scrollToBottom(true);
}

// Unicode解码函数
function decodeUnicode(str) {
    if (!str || typeof str !== 'string') return str;

    // 处理Unicode转义序列（如\\u6211\\u6765\\u4e3a\\u60a8）
    return str.replace(/\\u([\dA-F]{4})/gi, function (match, p1) {
        return String.fromCharCode(parseInt(p1, 16));
    });
}

// 添加消息到聊天界面（增加 skipScroll 参数）
function addMessageToChat(role, content, isStreaming = false, timestamp = null, forceId = null, skipScroll = false) {
    const messageId = forceId || ('msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9));

    const messageElement = document.createElement('div');
    messageElement.className = `message ${role}`;
    messageElement.id = messageId;

    const avatar = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
    const time = timestamp ? formatTime(timestamp) : formatTime(Date.now());


    messageElement.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-text">${isStreaming ? '<div class="streaming-indicator"><i class="fas fa-circle-notch fa-spin"></i> 思考中...</div>' : marked.parse(content)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;

    // 为非流式消息添加代码块复制功能
    if (!isStreaming) {
        const messageTextElement = messageElement.querySelector('.message-text');
        if (messageTextElement) {
            wrapCodeBlocks(messageTextElement);
            addCopyButtonsToCodeBlocks(messageTextElement);
            highlightCodeBlocks(messageTextElement);
        }
    }

    elements.messagesContainer.appendChild(messageElement);

    // 【修改点】：如果指定了 skipScroll 为 true，这里就不触发滚动
    if (!isStreaming && !skipScroll) {
        scrollToBottom();
    }

    return messageId;
}

// 更新消息内容（用于流式响应）
function updateMessageContent(messageId, content) {
    const messageElement = document.getElementById(`${messageId}`);
    if (!messageElement) return;

    const messageTextElement = messageElement.querySelector('.message-text');
    if (messageTextElement) {

        // 渲染Markdown并处理代码块
        const renderedContent = renderMarkdownWithCodeBlocks(content);
        messageTextElement.innerHTML = renderedContent;

        // 先包装代码块，再添加复制按钮
        wrapCodeBlocks(messageTextElement);
        addCopyButtonsToCodeBlocks(messageTextElement);

        // 重新高亮代码块
        highlightCodeBlocks(messageTextElement);
    }

    // 滚动到底部
    scrollToBottom();
}

// 渲染Markdown并处理代码块
function renderMarkdownWithCodeBlocks(content) {
    // 使用marked渲染Markdown
    let html = marked.parse(content);

    // 为代码块添加包装器
    html = html.replace(/<pre><code[^>]*>/g, '<div class="code-block-wrapper"><pre><code>');
    html = html.replace(/<\/code><\/pre>/g, '</code></pre></div>');

    return html;
}

// 包装代码块
function wrapCodeBlocks(container) {
    const codeBlocks = container.querySelectorAll('pre');

    codeBlocks.forEach(preElement => {
        // 如果已经包装过，跳过
        if (preElement.parentElement.classList.contains('code-block-wrapper')) {
            return;
        }

        // 创建包装器
        const wrapper = document.createElement('div');
        wrapper.className = 'code-block-wrapper';

        // 将pre元素移动到包装器中
        preElement.parentNode.insertBefore(wrapper, preElement);
        wrapper.appendChild(preElement);
    });
}

// 为代码块添加复制按钮
function addCopyButtonsToCodeBlocks(container) {
    const codeBlocks = container.querySelectorAll('.code-block-wrapper');

    codeBlocks.forEach((wrapper, index) => {
        // 如果已经添加了复制按钮，跳过
        if (wrapper.querySelector('.copy-code-btn')) {
            return;
        }

        const preElement = wrapper.querySelector('pre');
        const codeElement = wrapper.querySelector('code');

        if (!preElement || !codeElement) return;

        // 创建复制按钮
        const copyButton = document.createElement('button');
        copyButton.className = 'copy-code-btn';
        copyButton.innerHTML = '<i class="fas fa-copy"></i> 复制';
        copyButton.setAttribute('data-code-index', index);

        // 添加点击事件 - 使用更可靠的方式
        copyButton.addEventListener('click', function (event) {
            event.stopPropagation(); // 阻止事件冒泡
            event.preventDefault(); // 阻止默认行为

            // 获取代码内容 - 使用更可靠的方法
            let codeContent = '';
            if (codeElement) {
                codeContent = codeElement.textContent || codeElement.innerText;
            } else if (preElement) {
                codeContent = preElement.textContent || preElement.innerText;
            }

            if (codeContent.trim()) {
                copyCodeToClipboard(codeContent, copyButton);
            }
        });

        // 确保按钮添加到正确的位置
        wrapper.style.position = 'relative';
        wrapper.appendChild(copyButton);
    });
}

// 复制代码到剪贴板
function copyCodeToClipboard(code, button) {
    // 优先使用execCommand，避免跨域问题
    const textArea = document.createElement('textarea');
    textArea.value = code;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '0';
    document.body.appendChild(textArea);
    textArea.select();
    textArea.setSelectionRange(0, 99999); // 移动设备支持

    let success = false;

    try {
        // 尝试使用execCommand
        success = document.execCommand('copy');
    } catch (err) {
        console.error('execCommand复制失败:', err);
    }

    // 如果execCommand失败，尝试使用Clipboard API
    if (!success) {
        navigator.clipboard.writeText(code).then(() => {
            success = true;
        }).catch(err => {
            console.error('Clipboard API复制失败:', err);
        });
    }

    // 清理DOM
    document.body.removeChild(textArea);

    // 显示复制成功状态
    const originalText = button.innerHTML;
    button.innerHTML = '<i class="fas fa-check"></i> 已复制';
    button.classList.add('copied');

    // 2秒后恢复原状
    setTimeout(() => {
        button.innerHTML = originalText;
        button.classList.remove('copied');
    }, 2000);
}

// 高亮代码块
function highlightCodeBlocks(container) {
    const codeBlocks = container.querySelectorAll('pre code');

    codeBlocks.forEach(block => {
        // 如果已经高亮过，跳过
        if (block.classList.contains('hljs')) {
            return;
        }

        // 尝试检测语言
        const language = detectCodeLanguage(block.textContent);

        if (language && hljs.getLanguage(language)) {
            try {
                block.innerHTML = hljs.highlight(block.textContent, { language }).value;
                block.classList.add('hljs');
            } catch (err) {
                console.error('高亮错误:', err);
                // 如果指定语言高亮失败，使用自动检测
                block.innerHTML = hljs.highlightAuto(block.textContent).value;
                block.classList.add('hljs');
            }
        } else {
            // 使用自动检测
            block.innerHTML = hljs.highlightAuto(block.textContent).value;
            block.classList.add('hljs');
        }
    });
}

// 检测代码语言
function detectCodeLanguage(code) {
    const firstLine = code.split('\n')[0].trim();

    // 根据常见模式检测语言
    if (firstLine.includes('function') || firstLine.includes('const') || firstLine.includes('let') || firstLine.includes('var')) {
        return 'javascript';
    }
    if (firstLine.includes('def ') || firstLine.includes('import ') || firstLine.includes('class ')) {
        return 'python';
    }
    if (firstLine.includes('#include') || firstLine.includes('int main')) {
        return 'cpp';
    }
    if (firstLine.includes('public class') || firstLine.includes('import ')) {
        return 'java';
    }
    if (firstLine.includes('<?php') || firstLine.includes('echo ')) {
        return 'php';
    }
    if (firstLine.includes('<html') || firstLine.includes('<!DOCTYPE')) {
        return 'html';
    }
    if (firstLine.includes('SELECT') || firstLine.includes('INSERT')) {
        return 'sql';
    }

    return null; // 让highlight.js自动检测
}

// 显示模型选择弹窗
function showModelModal() {
    selectedModel = null;
    elements.confirmBtn.disabled = true;
    elements.modelModal.style.display = 'flex';

    // 取消之前的选择
    document.querySelectorAll('.model-item').forEach(item => {
        item.classList.remove('selected');
    });
}

// 隐藏模型选择弹窗
function hideModelModal() {
    elements.modelModal.style.display = 'none';
}

// 显示错误消息
function showError(message) {
    // 简单的错误提示，可以替换为更复杂的通知组件
    alert('错误: ' + message);
}

// 显示成功消息
function showSuccess(message) {
    // 简单的成功提示
    alert('成功: ' + message);
}

// 显示加载状态
function showLoading(show) {
    if (show) {
        elements.loadingOverlay.style.display = 'flex';
    } else {
        elements.loadingOverlay.style.display = 'none';
    }
}

// 更新字符计数
function updateCharCount() {
    const count = elements.messageInput.value.length;
    elements.charCount.textContent = `${count}/2000`;

    // 颜色提示
    if (count > 1800) {
        elements.charCount.style.color = '#e53e3e';
    } else if (count > 1500) {
        elements.charCount.style.color = '#dd6b20';
    } else {
        elements.charCount.style.color = '#718096';
    }
}

// 处理键盘事件
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// 格式化时间
function formatTime(timestamp) {
    // 后端返回的是std::time_t类型的整数时间戳（秒级），需要转换为毫秒
    // 先检查timestamp是否为有效数字
    if (!timestamp || isNaN(timestamp) || timestamp <= 0) {
        return '未知时间';
    }

    const date = new Date(timestamp * 1000);

    // 检查日期是否有效
    if (isNaN(date.getTime())) {
        console.error('无效的时间戳:', timestamp);
        return '未知时间';
    }

    const now = new Date();
    const diff = now - date;

    if (diff < 60000) { // 1分钟内
        return '刚刚';
    } else if (diff < 3600000) { // 1小时内
        return Math.floor(diff / 60000) + '分钟前';
    } else if (diff < 86400000) { // 1天内
        return Math.floor(diff / 3600000) + '小时前';
    } else if (diff < 604800000) { // 1周内
        return Math.floor(diff / 86400000) + '天前';
    } else {
        return date.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    }
}

// HTML 转义
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return unsafe.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// 在消息气泡底部追加一个音频播放器
function appendAudioPlayer(messageId, audioUrl) {
    const messageElement = document.getElementById(messageId);
    if (!messageElement) return;

    const contentDiv = messageElement.querySelector('.message-content');
    if (!contentDiv) return;

    // 创建播放器容器
    const audioContainer = document.createElement('div');
    audioContainer.className = 'audio-player-wrapper';
    audioContainer.style.marginTop = '12px';

    // 创建 audio 标签
    const audioEl = document.createElement('audio');
    audioEl.controls = true;
    audioEl.autoplay = true; // 获取到立刻自动播放！
    audioEl.src = audioUrl;
    audioEl.style.height = '40px';
    audioEl.style.width = '100%';
    audioEl.style.outline = 'none';

    audioContainer.appendChild(audioEl);
    contentDiv.appendChild(audioContainer);

    // 渲染播放器后，再次触发瞬间沉底滚动
    scrollToBottom(true);
}

// ==========================================
// 语音识别 (ASR) 核心逻辑
// ==========================================

// 切换录音状态
async function toggleRecording() {
    if (!currentSessionId) {
        showError('请先选择或创建会话');
        return;
    }

    if (isRecording) {
        stopRecording();
    } else {
        await startRecording();
    }
}

// 开始录音
async function startRecording() {
    try {
        // 请求麦克风权限
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        // 收集音频数据片段
        mediaRecorder.addEventListener('dataavailable', event => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        });

        // 停止录音时，触发发送逻辑
        mediaRecorder.addEventListener('stop', async () => {
            // 将片段打包成 Blob 文件 (通常为 webm 或 ogg 格式)
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

            // 释放麦克风资源
            stream.getTracks().forEach(track => track.stop());

            // 提交给后端识别
            await sendAudioToServer(audioBlob);
        });

        // 启动录制
        mediaRecorder.start();
        isRecording = true;

        // 更新 UI 为正在录音状态
        elements.recordBtn.classList.add('recording');
        elements.recordBtn.innerHTML = '<i class="fas fa-stop"></i>';
        elements.recordBtn.title = "点击结束录音";
        elements.messageInput.placeholder = '正在录音... 点击红色方块结束';
        elements.messageInput.disabled = true;

    } catch (err) {
        console.error('麦克风调用失败:', err);

        // 【优化错误提示，准确定位原因】
        if (err.name === 'NotAllowedError' || err.name === 'SecurityError') {
            showError('麦克风被拒绝。如果是通过 HTTP 协议非本地访问，浏览器会出于安全限制拦截麦克风。请使用 localhost 或 HTTPS 访问！');
        } else if (err.name === 'NotFoundError') {
            showError('未检测到麦克风设备，请检查硬件连接！');
        } else {
            showError('无法访问麦克风: ' + err.message);
        }
    }
}

// 停止录音
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    isRecording = false;

    // 更新 UI 为正在识别状态
    elements.recordBtn.classList.remove('recording');
    elements.recordBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    elements.recordBtn.title = "正在识别语音...";
    elements.messageInput.placeholder = '正在翻译成文字...';
}

// 发送音频至后端 ASR 接口
async function sendAudioToServer(audioBlob) {
    const formData = new FormData();
    // 添加文件对象，名称为 file
    formData.append('file', audioBlob, 'recording.webm');

    try {
        const response = await fetch(`${API_BASE_URL}/api/audio/recognize`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (data.success) {
            let recognizedText = data.data.text;

            // 【数据清洗】：处理返回内容中的 "上海话：xxx \n普通话：失败..."
            if (recognizedText.includes("上海话：")) {
                recognizedText = recognizedText.split("普通话：")[0].replace("上海话：", "").trim();
            }

            if (recognizedText) {
                // 将纯净文本填入输入框
                elements.messageInput.value = recognizedText;

                // 【无缝衔接】：直接调用文字发送接口！
                sendMessage();
            } else {
                showError("未能识别出有效的语音内容");
            }
        } else {
            showError('语音识别失败: ' + data.message);
        }
    } catch (error) {
        console.error('语音识别请求错误:', error);
        showError('语音识别网络错误，请稍后重试');
    } finally {
        // 恢复 UI 初始状态
        elements.recordBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        elements.recordBtn.title = "点击开始语音输入";
        elements.messageInput.placeholder = '输入消息...';
        elements.messageInput.disabled = false;
    }
}