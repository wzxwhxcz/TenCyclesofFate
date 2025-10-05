// 测试高级编辑功能的调试脚本

/**
 * 增强 fetchJSON 函数以添加详细日志
 */
const originalFetchJSON = window.fetchJSON;
window.fetchJSON = async function(url, options = {}) {
    // 记录请求详情
    if (url.includes('/update')) {
        console.group('[DEBUG] 更新请求');
        console.log('URL:', url);
        console.log('Method:', options.method);
        if (options.body) {
            try {
                const bodyData = JSON.parse(options.body);
                console.log('Body (parsed):', bodyData);
                console.log('字段数量:', Object.keys(bodyData).length);
                console.log('字段列表:', Object.keys(bodyData));
            } catch (e) {
                console.log('Body (raw):', options.body);
            }
        }
        console.groupEnd();
    }

    // 调用原始函数
    const result = await originalFetchJSON.call(this, url, options);

    // 记录响应
    if (url.includes('/update')) {
        console.group('[DEBUG] 更新响应');
        console.log('响应数据:', result);
        console.groupEnd();
    }

    return result;
};

/**
 * 增强 saveEdit 函数以添加详细日志
 */
const originalSaveEdit = window.saveEdit;
window.saveEdit = async function() {
    console.group('[DEBUG] 保存编辑开始');

    // 收集游戏状态编辑器的数据
    const gameStateTextarea = document.getElementById('edit-game-state');
    if (gameStateTextarea) {
        console.log('游戏状态 textarea 内容:', gameStateTextarea.value);
        if (gameStateTextarea.value.trim()) {
            try {
                const parsed = JSON.parse(gameStateTextarea.value);
                console.log('游戏状态解析成功:', parsed);
                console.log('游戏状态字段:', Object.keys(parsed));
            } catch (e) {
                console.error('游戏状态解析失败:', e);
            }
        }
    }

    // 收集试炼历史
    const trialHistoryTextarea = document.getElementById('edit-trial-history');
    if (trialHistoryTextarea && trialHistoryTextarea.value.trim()) {
        console.log('试炼历史:', trialHistoryTextarea.value);
    }

    console.groupEnd();

    // 调用原始函数
    return await originalSaveEdit.call(this);
};

/**
 * 监听游戏状态编辑器的变化
 */
function monitorGameStateEditor() {
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList' || mutation.type === 'attributes') {
                const textarea = document.getElementById('edit-game-state');
                if (textarea) {
                    const currentValue = textarea.value;
                    if (currentValue && currentValue !== window.lastGameStateValue) {
                        console.log('[MONITOR] 游戏状态更新:', currentValue);
                        window.lastGameStateValue = currentValue;
                    }
                }
            }
        });
    });

    const editorContainer = document.getElementById('game-state-editor');
    if (editorContainer) {
        observer.observe(editorContainer, {
            childList: true,
            subtree: true,
            attributes: true
        });
        console.log('[MONITOR] 开始监控游戏状态编辑器');
    }
}

/**
 * 手动验证更新函数
 */
window.testUpdateSession = async function(playerId, updates) {
    console.group('[TEST] 手动测试更新会话');
    console.log('Player ID:', playerId);
    console.log('Updates:', updates);

    try {
        const response = await fetch(`/api/admin/sessions/${encodeURIComponent(playerId)}/update`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        const result = await response.json();
        console.log('响应状态:', response.status);
        console.log('响应数据:', result);

        // 重新获取会话数据验证更新
        const sessionResponse = await fetch(`/api/admin/sessions/${encodeURIComponent(playerId)}`, {
            credentials: 'include'
        });
        const sessionData = await sessionResponse.json();
        console.log('更新后的会话数据:', sessionData);

        // 验证字段是否更新
        for (const key in updates) {
            if (sessionData[key] === updates[key]) {
                console.log(`✅ 字段 ${key} 更新成功`);
            } else {
                console.error(`❌ 字段 ${key} 更新失败. 期望: ${updates[key]}, 实际: ${sessionData[key]}`);
            }
        }
    } catch (error) {
        console.error('测试失败:', error);
    }

    console.groupEnd();
};

// 启动监控
setTimeout(() => {
    monitorGameStateEditor();
    console.log('🔧 调试脚本已加载');
    console.log('使用方法:');
    console.log('1. 打开高级编辑器，修改字段');
    console.log('2. 查看控制台日志了解数据流');
    console.log('3. 使用 testUpdateSession("player_id", {field: value}) 手动测试');
}, 1000);