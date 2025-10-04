// --- Constants ---
const API_BASE_URL = "/api";

// --- State Management ---
const appState = {
    gameState: null,
    streamBuffer: '',  // 鐢ㄤ簬瀛樺偍娴佸紡杈撳嚭鐨勭紦鍐插尯
    isStreaming: false,  // 鏍囪鏄惁姝ｅ湪鎺ユ敹娴佸紡杈撳嚭
};
// 过滤函数：在流式显示中永远不展示任何代码块/JSON
function sanitizeStreamText(text) {
    if (!text) return '';
    // 移除所有围栏代码块 `...`（包含 `json）
    let s = text.replace(/`[\s\S]*?`/g, '');
    // 若出现未闭合的围栏，从起始 ` 到结尾全部移除
    s = s.replace(/`[\s\S]*$/g, '');
    return s;
}

// --- DOM Elements ---
function filterStreamForDisplay(text) {
    if (!text) return '';
    // Remove fenced code blocks like ```...``` including ```json
    let s = text.replace(new RegExp('```[\\s\\S]*?```','g'), '');
    // If fence starts but not closed yet, drop tail from first ```
    s = s.replace(new RegExp('```[\\s\\S]*$','g'), '');
    return s;
}

const DOMElements = {
    loginView: document.getElementById('login-view'),
    gameView: document.getElementById('game-view'),
    loginError: document.getElementById('login-error'),
    logoutButton: document.getElementById('logout-button'),
    narrativeWindow: document.getElementById('narrative-window'),
    characterStatus: document.getElementById('character-status'),
    opportunitiesSpan: document.getElementById('opportunities'),
    actionInput: document.getElementById('action-input'),
    actionButton: document.getElementById('action-button'),
    startTrialButton: document.getElementById('start-trial-button'),
    loadingSpinner: document.getElementById('loading-spinner'),
    rollOverlay: document.getElementById('roll-overlay'),
    rollPanel: document.getElementById('roll-panel'),
    rollType: document.getElementById('roll-type'),
    rollTarget: document.getElementById('roll-target'),
    rollResultDisplay: document.getElementById('roll-result-display'),
    rollOutcome: document.getElementById('roll-outcome'),
    rollValue: document.getElementById('roll-value'),
};

// --- API Client ---
const api = {
    async initGame() {
        const response = await fetch(`${API_BASE_URL}/game/init`, {
            method: 'POST',
            // No Authorization header needed, relies on HttpOnly cookie
        });
        if (response.status === 401) {
            throw new Error('Unauthorized');
        }
        if (!response.ok) throw new Error('Failed to initialize game session');
        return response.json();
    },
    async logout() {
        await fetch(`${API_BASE_URL}/logout`, { method: 'POST' });
        window.location.href = '/';
    }
};

// --- WebSocket Manager ---
const socketManager = {
    socket: null,
    _ensureStreamingElements() {
        const container = DOMElements.narrativeWindow;
        let indicator = document.getElementById('streaming-indicator');
        let display = document.getElementById('stream-display');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'streaming-indicator';
            indicator.textContent = 'AI 姝ｅ湪鐢熸垚鈥?;
            indicator.style.opacity = '0.7';
            indicator.style.fontSize = '0.9em';
            container.appendChild(indicator);
        }
        if (!display) {
            display = document.createElement('div');
            display.id = 'stream-display';
            container.appendChild(display);
        }
        return { indicator, display };
    },
    _removeStreamingElements() {
        const indicator = document.getElementById('streaming-indicator');
        const display = document.getElementById('stream-display');
        if (indicator && indicator.parentElement) indicator.parentElement.removeChild(indicator);
        if (display && display.parentElement) display.parentElement.removeChild(display);
    },
    connect() {
        return new Promise((resolve, reject) => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                resolve();
                return;
            }
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            // The token is no longer in the URL; it's read from the cookie by the server.
            const wsUrl = `${protocol}//${host}${API_BASE_URL}/ws`;
            this.socket = new WebSocket(wsUrl);
            this.socket.binaryType = 'arraybuffer'; // Important for receiving binary data

            this.socket.onopen = () => { console.log("WebSocket established."); resolve(); };
            this.socket.onmessage = (event) => {
                let message;
                // Check if the data is binary (ArrayBuffer)
                if (event.data instanceof ArrayBuffer) {
                    try {
                        // Decompress the gzip data using pako.ungzip
                        const decompressed = pako.ungzip(new Uint8Array(event.data), { to: 'string' });
                        message = JSON.parse(decompressed);
                    } catch (err) {
                        console.error('Failed to decompress or parse message:', err);
                        return;
                    }
                } else {
                    // Fallback for non-binary messages
                    message = JSON.parse(event.data);
                }
                
                switch (message.type) {
                    case 'full_state':
                        appState.gameState = message.data;
                        render();
                        break;
                    case 'roll_event': // Listen for the separate, immediate roll event
                        renderRollEvent(message.data);
                        break;
                    case 'stream_start':
                        // 寮€濮嬫祦寮忚緭鍑?                        appState.isStreaming = true;
                        appState.streamBuffer = '';
                        // 涓嶅啀鏄剧ず璋冭瘯鎸囩ず鍣?                        break;
                    case 'stream_chunk':
                        // 鎺ユ敹娴佸紡鏁版嵁鍧?                        if (appState.isStreaming && message.data && message.data.content) {
                            appState.streamBuffer += message.data.content;
                            // 涓嶅啀鏄剧ず娴佸紡鍐呭
                        }
                        break;
                    case 'stream_end':
                        // 结束流式输出（保留缓冲，待 full_state 到来由 render() 清理）
                        appState.isStreaming = false;
                        break;
                    case 'error':
                        alert(`WebSocket Error: ${message.detail}`);
                        break;
                }

                // 澧炲己鐨勬祦寮廢I娓叉煋锛堜笌鐜版湁鐘舵€佸鐞嗚В鑰︼紝閬垮厤闃诲锛?                if (message.type === 'stream_start') {
                    // 闅愯棌鍏ㄥ眬鍔犺浇锛屽垱寤烘祦寮忓鍣?                    showLoading(false);
                    socketManager._ensureStreamingElements();
                } else if (message.type === 'stream_chunk') {
                    if (appState.isStreaming && message.data && message.data.content) {
                        const els = socketManager._ensureStreamingElements();
                        const sanitized = filterStreamForDisplay(appState.streamBuffer);
                        els.display.innerHTML = marked.parse(sanitized);
                        DOMElements.narrativeWindow.scrollTop = DOMElements.narrativeWindow.scrollHeight;
                    }
                } else if (message.type === 'stream_end') {
                    // 淇濈暀宸叉樉绀哄唴瀹癸紝寰?full_state 鍒版潵鍚庣敱 render() 缁熶竴娓呯悊
                }
            };
            this.socket.onclose = () => { console.log("Reconnecting..."); showLoading(true); setTimeout(() => this.connect(), 5000); };
            this.socket.onerror = (error) => { console.error("WebSocket error:", error); DOMElements.loginError.textContent = '鏃犳硶杩炴帴銆?; reject(error); };
        });
    },
    sendAction(action) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ action }));
        } else {
            alert("杩炴帴宸叉柇寮€锛岃鍒锋柊銆?);
        }
    }
};

// --- UI & Rendering ---
function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');
}

function showLoading(isLoading) {
    // 濡傛灉姝ｅ湪娴佸紡杈撳嚭锛屼笉鏄剧ず鍔犺浇鍔ㄧ敾
    if (appState.isStreaming) {
        DOMElements.loadingSpinner.style.display = 'none';
    } else {
        DOMElements.loadingSpinner.style.display = isLoading ? 'flex' : 'none';
    }
    const isProcessing = appState.gameState ? appState.gameState.is_processing : false;
    const buttonsDisabled = isLoading || isProcessing || appState.isStreaming;
    // DOMElements.loginButton is removed
    DOMElements.actionInput.disabled = buttonsDisabled;
    DOMElements.actionButton.disabled = buttonsDisabled;
    DOMElements.startTrialButton.disabled = buttonsDisabled;
}

function render() {
    if (!appState.gameState) { showLoading(true); return; }
    showLoading(appState.gameState.is_processing);
    DOMElements.opportunitiesSpan.textContent = appState.gameState.opportunities_remaining;
    renderCharacterStatus();

    const historyContainer = document.createDocumentFragment();
    (appState.gameState.display_history || []).forEach(text => {
        const p = document.createElement('div');
        p.innerHTML = marked.parse(text);
        if (text.startsWith('> ')) p.classList.add('user-input-message');
        else if (text.startsWith('銆?)) p.classList.add('system-message');
        historyContainer.appendChild(p);
    });
    DOMElements.narrativeWindow.innerHTML = '';
    DOMElements.narrativeWindow.appendChild(historyContainer);
    // 濡傛灉浠嶅湪娴佸紡杩囩▼涓紝缁х画鍦ㄥ熬閮ㄦ樉绀哄凡鎺ユ敹鐗囨锛涘惁鍒欐竻鐞嗘畫鐣?    if (appState.isStreaming && appState.streamBuffer) {
        const els = socketManager._ensureStreamingElements();
        const sanitized = filterStreamForDisplay(appState.streamBuffer);
        els.display.innerHTML = marked.parse(sanitized);
    } else {
        socketManager._removeStreamingElements();
        appState.streamBuffer = '';
    }
    DOMElements.narrativeWindow.scrollTop = DOMElements.narrativeWindow.scrollHeight;
    
    const { is_in_trial, daily_success_achieved, opportunities_remaining } = appState.gameState;
    DOMElements.actionInput.parentElement.classList.toggle('hidden', !(is_in_trial || daily_success_achieved || opportunities_remaining < 0));
    const startButton = DOMElements.startTrialButton;
    startButton.classList.toggle('hidden', is_in_trial || daily_success_achieved || opportunities_remaining < 0);

    if (daily_success_achieved) {
         startButton.textContent = "浠婃棩鍔熷痉鍦嗘弧";
         startButton.disabled = true;
    } else if (opportunities_remaining <= 0) {
        startButton.textContent = "鏈虹紭宸插敖";
        startButton.disabled = true;
    } else {
        if (opportunities_remaining === 10) {
            startButton.textContent = "寮€濮嬬涓€娆¤瘯鐐?;
        } else {
            startButton.textContent = "寮€鍚笅涓€娆¤瘯鐐?;
        }
        startButton.disabled = appState.gameState.is_processing;
    }
}

function renderValue(container, value, level = 0) {
    if (Array.isArray(value)) {
        value.forEach(item => renderValue(container, item, level + 1));
    } else if (typeof value === 'object' && value !== null) {
        const subContainer = document.createElement('div');
        subContainer.style.paddingLeft = `${level * 10}px`;
        Object.entries(value).forEach(([key, val]) => {
            const propDiv = document.createElement('div');
            propDiv.classList.add('property-item');
            
            const keySpan = document.createElement('span');
            keySpan.classList.add('property-key');
            keySpan.textContent = `${key}: `;
            propDiv.appendChild(keySpan);

            // Recursively render the value
            renderValue(propDiv, val, level + 1);
            subContainer.appendChild(propDiv);
        });
        container.appendChild(subContainer);
    } else {
        const valueSpan = document.createElement('span');
        valueSpan.classList.add('property-value');
        valueSpan.textContent = value;
        container.appendChild(valueSpan);
    }
}

function renderCharacterStatus() {
    const { current_life } = appState.gameState;
    const container = DOMElements.characterStatus;
    container.innerHTML = ''; // Clear previous content

    if (!current_life) {
        container.textContent = '闈欏緟澶╁懡...';
        return;
    }

    Object.entries(current_life).forEach(([key, value]) => {
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.textContent = key;
        details.appendChild(summary);

        const content = document.createElement('div');
        content.classList.add('details-content');
        
        renderValue(content, value);
        
        details.appendChild(content);
        container.appendChild(details);
    });
}

function renderRollEvent(rollEvent) {
    DOMElements.rollType.textContent = `鍒ゅ畾: ${rollEvent.type}`;
    DOMElements.rollTarget.textContent = `(<= ${rollEvent.target})`;
    DOMElements.rollOutcome.textContent = rollEvent.outcome;
    DOMElements.rollOutcome.className = `outcome-${rollEvent.outcome}`;
    DOMElements.rollValue.textContent = rollEvent.result;
    DOMElements.rollResultDisplay.classList.add('hidden');
    DOMElements.rollOverlay.classList.remove('hidden');
    setTimeout(() => DOMElements.rollResultDisplay.classList.remove('hidden'), 1000);
    setTimeout(() => DOMElements.rollOverlay.classList.add('hidden'), 3000);
}

// 绉婚櫎璋冭瘯鐢ㄧ殑娴佸紡UI鍑芥暟锛岃繖浜涗笉搴旇鍦ㄧ敓浜х幆澧冧腑鏄剧ず

// --- Event Handlers ---
function handleLogout() {
    api.logout();
}

function handleAction(actionOverride = null) {
    const action = actionOverride || DOMElements.actionInput.value.trim();
    if (!action) return;

    // Special case for starting a trial to prevent getting locked out by is_processing flag
    if (action === "寮€濮嬭瘯鐐?) {
        // Allow starting a new trial even if the previous async task is in its finally block
    } else {
        // For all other actions, prevent sending if another action is in flight.
        if (appState.gameState && appState.gameState.is_processing) return;
    }

    DOMElements.actionInput.value = '';
    socketManager.sendAction(action);
}

// --- Initialization ---
async function initializeGame() {
    showLoading(true);
    try {
        const initialState = await api.initGame();
        appState.gameState = initialState;
        render();
        showView('game-view');
        await socketManager.connect();
        console.log("Initialization complete and WebSocket is ready.");
    } catch (error) {
        // If init fails (e.g. no valid cookie), just show the login view.
        // The api.initGame function no longer redirects, it just throws an error.
        showView('login-view');
        if (error.message !== 'Unauthorized') {
             console.error(`Session initialization failed: ${error.message}`);
        }
    } finally {
        // Ensure spinner is hidden regardless of outcome
        showLoading(false);
    }
    
    // 娓呯悊浠讳綍鍙兘娈嬬暀鐨勮皟璇曟樉绀哄厓绱?    const indicator = document.getElementById('streaming-indicator');
    if (indicator) {
        indicator.remove();
    }
    const streamDisplay = document.getElementById('stream-display');
    if (streamDisplay) {
        streamDisplay.remove();
    }
}

function init() {
    // Always try to initialize the game on page load.
    // If the user is logged in, it will show the game view.
    // If not, the catch block in initializeGame will handle showing the login view.
    initializeGame();

    // Setup event listeners regardless of initial view
    DOMElements.logoutButton.addEventListener('click', handleLogout);
    DOMElements.actionButton.addEventListener('click', () => handleAction());
    DOMElements.actionInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleAction(); });
    DOMElements.startTrialButton.addEventListener('click', () => handleAction("寮€濮嬭瘯鐐?));
}

// --- Start the App ---
init();





