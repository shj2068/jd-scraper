/**
 * 反检测注入脚本模块
 * 
 * 提供 Playwright 反检测注入脚本，覆盖 navigator.webdriver、plugins、
 * languages、chrome.runtime 等浏览器特征，消除自动化痕迹。
 * 
 * v2.0 增强（文档第三章/第四章参考）：
 * - Canvas 指纹像素扰动（真实 noise 注入，非简单 hash）
 * - WebGL UNMASKED_VENDOR/RENDERER 真实覆盖
 * - 鼠标轨迹模拟（Bezier 曲线随机移动）
 * - AudioContext 指纹抖动
 */

'use strict';

/**
 * 生成完整的反检测注入脚本
 * @param {Object} options - 配置选项
 * @param {string} options.platform - 平台类型 (win32/mac/linux)
 * @param {string} options.language - 语言
 * @param {number} options.hardwareConcurrency - CPU 核心数
 * @param {string} options.webglVendor - WebGL 厂商
 * @param {string} options.webglRenderer - WebGL 渲染器
 * @returns {Function} 注入脚本函数
 */
function createStealthScript(options = {}) {
    const platform = options.platform || 'Win32';
    const language = options.language || 'zh-CN';
    const languages = options.languages || ['zh-CN', 'zh', 'en'];
    const hardwareConcurrency = options.hardwareConcurrency || 8;
    const webglVendor = options.webglVendor || 'Google Inc. (NVIDIA)';
    const webglRenderer = options.webglRenderer || 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)';

    return () => {
        // ===== 1. 基础反检测 =====

        // 1.1 覆盖 navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true,
        });

        // 1.2 覆盖 navigator.plugins
        const mockPlugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' },
        ];

        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = mockPlugins.map(p => ({
                    name: p.name,
                    filename: p.filename,
                    description: '',
                    length: 1,
                }));
                plugins.refresh = () => {};
                return plugins;
            },
            configurable: true,
        });

        // 1.3 覆盖 navigator.languages
        Object.defineProperty(navigator, 'languages', {
            get: () => Object.freeze(languages),
            configurable: true,
        });

        // 1.4 覆盖 navigator.platform
        Object.defineProperty(navigator, 'platform', {
            get: () => platform,
            configurable: true,
        });

        // 1.5 覆盖 navigator.hardwareConcurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => hardwareConcurrency,
            configurable: true,
        });

        // 1.6 注入 window.chrome
        window.chrome = {
            runtime: {
                onConnect: { addListener: () => {}, removeListener: () => {} },
                onMessage: { addListener: () => {}, removeListener: () => {} },
                sendMessage: () => {},
                connect: () => {},
            },
            loadTimes: function() {
                return {
                    requestTime: Date.now() / 1000,
                    startLoadTime: Date.now() / 1000,
                    commitLoadTime: Date.now() / 1000,
                    finishDocumentLoadTime: Date.now() / 1000,
                    finishLoadTime: Date.now() / 1000,
                    firstPaintTime: Date.now() / 1000,
                    navigationType: 'Other',
                    wasFetchedViaSpdy: false,
                    wasNpnNegotiated: false,
                    connectionInfo: 'http/1.1',
                };
            },
            csi: function() {
                return {
                    startE: Date.now(),
                    onloadT: Date.now(),
                    pageT: Date.now(),
                    tran: 15,
                };
            },
        };

        // 1.7 覆盖 Permissions API
        const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
        if (originalQuery) {
            window.navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({ state: Notification.permission });
                }
                return originalQuery(parameters);
            };
        }

        // 1.8 消除 CDP 调试痕迹
        const cdpProps = Object.keys(window).filter(k =>
            k.startsWith('cdc_') || k.startsWith('__selenium_') || k.startsWith('__webdriver_')
        );
        cdpProps.forEach(prop => {
            try { delete window[prop]; } catch(e) {}
        });

        // 1.9 覆盖 toString 检测
        const originalToString = Function.prototype.toString;
        Function.prototype.toString = function() {
            if (this === Function.prototype.toString) return 'function toString() { [native code] }';
            return originalToString.call(this);
        };

        // ===== 2. Canvas 指纹像素扰动（文档第三章 3.2 节）=====
        // 真实 noise 注入，非简单 hash 替换
        const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        const _origToBlob = HTMLCanvasElement.prototype.toBlob;
        const _origGetImageData = CanvasRenderingContext2D.prototype.getImageData;

        // 像素级扰动：对 Canvas 渲染结果的每个像素添加微小噪声
        function perturbCanvasData(imageData) {
            const data = imageData.data;
            for (let i = 0; i < data.length; i += 4) {
                // 仅扰动 RGB，不改 Alpha
                // 扰动幅度: ±1（人眼不可见，但指纹哈希完全不同）
                const noise = (Math.random() > 0.5) ? 1 : -1;
                data[i]     = Math.max(0, Math.min(255, data[i]     + noise)); // R
                data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + noise)); // G
                data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + noise)); // B
            }
            return imageData;
        }

        CanvasRenderingContext2D.prototype.getImageData = function(...args) {
            const imageData = _origGetImageData.apply(this, args);
            return perturbCanvasData(imageData);
        };

        HTMLCanvasElement.prototype.toDataURL = function(...args) {
            // 先触发一次 getImageData 扰动
            try {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const w = this.width || 300;
                    const h = this.height || 150;
                    ctx.getImageData(0, 0, w, h); // 触发扰动
                }
            } catch(e) {}
            return _origToDataURL.apply(this, args);
        };

        HTMLCanvasElement.prototype.toBlob = function(...args) {
            try {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const w = this.width || 300;
                    const h = this.height || 150;
                    ctx.getImageData(0, 0, w, h);
                }
            } catch(e) {}
            return _origToBlob.apply(this, args);
        };

        // ===== 3. WebGL 指纹真实覆盖（文档第三章 3.3 节）=====
        const webglDebugInfo = { vendor: webglVendor, renderer: webglRenderer };

        const _origGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // UNMASKED_VENDOR_WEBGL = 0x9245
            if (parameter === 37445) {
                return webglDebugInfo.vendor;
            }
            // UNMASKED_RENDERER_WEBGL = 0x9246
            if (parameter === 37446) {
                return webglDebugInfo.renderer;
            }
            return _origGetParameter.apply(this, [parameter]);
        };

        // WebGL2 也需要覆盖
        if (typeof WebGL2RenderingContext !== 'undefined') {
            const _origGetParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return webglDebugInfo.vendor;
                if (parameter === 37446) return webglDebugInfo.renderer;
                return _origGetParameter2.apply(this, [parameter]);
            };
        }

        // ===== 4. AudioContext 指纹抖动 =====
        const _origCreateOscillator = AudioContext.prototype.createOscillator;
        AudioContext.prototype.createOscillator = function(...args) {
            const osc = _origCreateOscillator.apply(this, args);
            // 微小频率偏移，影响 AudioContext 指纹但不影响可听范围
            const origConnect = osc.connect.bind(osc);
            osc.connect = function(dest) {
                try { osc.detune.value += (Math.random() - 0.5) * 0.001; } catch(e) {}
                return origConnect(dest);
            };
            return osc;
        };

        // ===== 5. 鼠标轨迹模拟（Bezier 曲线）=====
        // 京东会检测鼠标移动轨迹是否自然
        window.__jdMouseSim = {
            /**
             * 生成 Bezier 曲线鼠标移动轨迹
             * @param {number} startX - 起点 X
             * @param {number} startY - 起点 Y
             * @param {number} endX - 终点 X
             * @param {number} endY - 终点 Y
             * @param {number} steps - 步数（默认 20-40）
             * @returns {Array} [{x, y, t}, ...]
             */
            generateBezierPath: function(startX, startY, endX, endY, steps) {
                steps = steps || (20 + Math.floor(Math.random() * 20));
                // 随机控制点（模拟人类弧线运动）
                const cp1x = startX + (endX - startX) * 0.25 + (Math.random() - 0.5) * 50;
                const cp1y = startY + (endY - startY) * 0.25 + (Math.random() - 0.5) * 50;
                const cp2x = startX + (endX - startX) * 0.75 + (Math.random() - 0.5) * 30;
                const cp2y = startY + (endY - startY) * 0.75 + (Math.random() - 0.5) * 30;

                const path = [];
                for (let i = 0; i <= steps; i++) {
                    const t = i / steps;
                    const u = 1 - t;
                    // 三次 Bezier 插值
                    const x = u*u*u*startX + 3*u*u*t*cp1x + 3*u*t*t*cp2x + t*t*t*endX;
                    const y = u*u*u*startY + 3*u*u*t*cp1y + 3*u*t*t*cp2y + t*t*t*endY;
                    // 添加微小抖动（人类手部微颤）
                    const jx = x + (Math.random() - 0.5) * 2;
                    const jy = y + (Math.random() - 0.5) * 2;
                    path.push({ x: Math.round(jx), y: Math.round(jy), t: t });
                }
                return path;
            },

            /**
             * 在页面元素上模拟真实鼠标移入/移出事件
             * @param {Element} element - 目标 DOM 元素
             */
            simulateHover: function(element) {
                if (!element) return;
                const rect = element.getBoundingClientRect();
                const targetX = rect.left + rect.width / 2 + (Math.random() - 0.5) * 10;
                const targetY = rect.top + rect.height / 2 + (Math.random() - 0.5) * 10;
                const startX = Math.random() * window.innerWidth;
                const startY = Math.random() * window.innerHeight;

                const path = this.generateBezierPath(startX, startY, targetX, targetY);
                let i = 0;
                const interval = setInterval(() => {
                    if (i >= path.length) {
                        clearInterval(interval);
                        // 到达目标，触发 mouseenter/mouseover
                        element.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true, clientX: targetX, clientY: targetY }));
                        element.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, clientX: targetX, clientY: targetY }));
                        return;
                    }
                    const p = path[i];
                    document.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: p.x, clientY: p.y }));
                    i++;
                }, 10 + Math.random() * 15); // 10-25ms 间隔
            }
        };

        logger && logger.debug && logger.debug('stealth.js v2.0 注入完成: Canvas/WebGL/Audio/Mouse');
    };
}

/**
 * 生成简化的反检测脚本
 */
function createMinimalStealthScript() {
    return () => {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {
            get: () => ['zh-CN', 'zh', 'en'],
        });
    };
}

/**
 * 获取 Playwright launch 参数
 */
function getStealthLaunchArgs() {
    return [
        '--disable-blink-features=AutomationControlled',
        '--disable-features=IsolateOrigins,site-per-process',
        '--disable-site-isolation-trials',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--lang=zh-CN',
        '--disable-extensions',
        '--disable-default-apps',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        // v2.0 新增：进一步消除自动化特征
        '--disable-infobars',
        '--hide-scrollbars',
        '--mute-audio',
        '--disable-notifications',
        '--disable-popup-blocking',
    ];
}

module.exports = {
    createStealthScript,
    createMinimalStealthScript,
    getStealthLaunchArgs,
};
