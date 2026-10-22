/**
 * h5st 签名执行 Worker 模块
 * 
 * 在浏览器上下文中执行 h5st 签名生成，
 * 自动定位页面中的签名方法，提供超时保护与错误捕获。
 */

'use strict';

const { createStealthScript } = require('./stealth');

/**
 * 签名 Worker 类
 */
class SignWorker {
    /**
     * @param {Object} page - Playwright Page 对象
     * @param {Object} options - 配置选项
     */
    constructor(page, options = {}) {
        this.page = page;
        this.timeout = options.timeout || 5000;
        this.targetUrl = options.targetUrl || 'https://zhaoshang.jd.com/';
        this.isReady = false;
        this.signFunctionName = options.signFunctionName || null;
    }

    /**
     * 初始化 Worker（加载页面并注入脚本）
     */
    async init() {
        try {
            // 注入反检测脚本
            const stealthScript = createStealthScript();
            await this.page.addInitScript(stealthScript);

            // 导航到目标页面
            await this.page.goto(this.targetUrl, {
                waitUntil: 'networkidle',
                timeout: 30000,
            });

            // 尝试定位签名函数
            if (this.signFunctionName) {
                const hasFunction = await this._checkFunctionExists(this.signFunctionName);
                if (!hasFunction) {
                    console.warn(`签名函数 ${this.signFunctionName} 不存在，尝试自动检测`);
                    this.signFunctionName = await this._autoDetectSignFunction();
                }
            } else {
                this.signFunctionName = await this._autoDetectSignFunction();
            }

            this.isReady = true;
            console.log(`SignWorker 初始化完成, 签名函数: ${this.signFunctionName || '未找到'}`);
        } catch (error) {
            console.error('SignWorker 初始化失败:', error.message);
            throw error;
        }
    }

    /**
     * 执行签名
     * @param {Object} params - 签名参数
     * @param {string} params.functionId - 接口名称
     * @param {string} params.body - 业务参数 JSON
     * @param {string} params.uuid - 设备 UUID
     * @param {string} params.t - 时间戳
     * @returns {Promise<Object>} 签名结果
     */
    async sign(params) {
        if (!this.isReady) {
            throw new Error('SignWorker 未初始化');
        }

        const { functionId, body, uuid, t } = params;

        try {
            // 使用 Promise.race 实现超时控制
            const signPromise = this._executeSign(functionId, body, uuid, t);
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('签名超时')), this.timeout);
            });

            const result = await Promise.race([signPromise, timeoutPromise]);
            return result;
        } catch (error) {
            console.error('签名执行失败:', error.message);
            return {
                code: -1,
                h5st: '',
                error: error.message,
            };
        }
    }

    /**
     * 内部方法：执行签名
     */
    async _executeSign(functionId, body, uuid, t) {
        // 策略 1: 使用提取的 ParamsSign 函数 (v5.3)
        try {
            // 等待 ParamsSign 加载（最多 3 秒）
            await this.page.waitForFunction(() => typeof window.ParamsSign === 'function', { timeout: 3000 }).catch(() => {});
            
            const result = await this.page.evaluate(async ({ fid, b, ts, uid }) => {
                if (typeof window.ParamsSign !== 'function') {
                    return { error: 'ParamsSign not available' };
                }
                try {
                    const signer = new window.ParamsSign();
                    const signResult = await signer.sign({
                        functionId: fid,
                        body: b,
                        t: ts,
                        uuid: uid
                    });
                    return signResult;
                } catch (e) {
                    return { error: e.message };
                }
            }, { fid: functionId, b: body, ts: t, uid: uuid });

            if (result && result.h5st) {
                return { code: 0, h5st: result.h5st, t, _stk: result._stk, _ste: result._ste };
            }
            if (result && result.error) {
                console.warn('ParamsSign 签名错误:', result.error);
            }
        } catch (e) {
            console.warn('ParamsSign 签名失败:', e.message);
        }

        // 策略 2: 调用已知的签名函数
        if (this.signFunctionName) {
            try {
                const h5st = await this.page.evaluate(({ fnName, fid, b, ts, uid }) => {
                    const fn = window[fnName];
                    if (typeof fn === 'function') {
                        return fn(fid, b, ts, uid);
                    }
                    return null;
                }, { fnName: this.signFunctionName, fid: functionId, b: body, ts: t, uid: uuid });

                if (h5st) {
                    return { code: 0, h5st, t };
                }
            } catch (e) {
                console.warn(`调用 ${this.signFunctionName} 失败:`, e.message);
            }
        }

        // 策略 3: 拦截网络请求获取 h5st
        try {
            const h5st = await this._interceptH5st(functionId, body, uuid, t);
            if (h5st) {
                return { code: 0, h5st, t };
            }
        } catch (e) {
            console.warn('拦截 h5st 失败:', e.message);
        }

        // 策略 4: 返回空 h5st（降级模式）
        return {
            code: 0,
            h5st: '',
            t,
            warning: 'h5st 生成失败，使用降级模式',
        };
    }

    /**
     * 通过网络拦截获取 h5st
     */
    async _interceptH5st(functionId, body, uuid, t) {
        return new Promise((resolve, reject) => {
            let captured = false;

            const handler = (request) => {
                const url = request.url();
                if (url.includes('api.m.jd.com') && !captured) {
                    const postData = request.postData();
                    if (postData && postData.includes(functionId)) {
                        captured = true;
                        // 从请求参数中提取 h5st
                        const params = new URLSearchParams(postData);
                        const h5st = params.get('h5st');
                        if (h5st) {
                            resolve(h5st);
                        }
                    }
                }
            };

            this.page.on('request', handler);

            // 超时清理
            setTimeout(() => {
                this.page.off('request', handler);
                if (!captured) {
                    reject(new Error('拦截超时'));
                }
            }, this.timeout);
        });
    }

    /**
     * 检查函数是否存在
     */
    async _checkFunctionExists(fnName) {
        try {
            return await this.page.evaluate((name) => {
                return typeof window[name] === 'function';
            }, fnName);
        } catch {
            return false;
        }
    }

    /**
     * 自动检测签名函数
     */
    async _autoDetectSignFunction() {
        try {
            return await this.page.evaluate(() => {
                // 优先检测 ParamsSign（h5st v5.3 签名构造器）
                if (typeof window.ParamsSign === 'function') {
                    return 'ParamsSign';
                }

                // 常见的签名函数名
                const candidates = [
                    'getH5st', 'h5st', 'sign', 'getSign',
                    'JD_SIGN', 'jdSign', '_jd_sign',
                ];

                for (const name of candidates) {
                    if (typeof window[name] === 'function') {
                        return name;
                    }
                }

                // 搜索全局对象中的签名相关函数
                for (const key of Object.keys(window)) {
                    if (key.toLowerCase().includes('h5st') || 
                        key.toLowerCase().includes('sign')) {
                        if (typeof window[key] === 'function') {
                            return key;
                        }
                    }
                }

                return null;
            });
        } catch {
            return null;
        }
    }

    /**
     * 获取 Worker 状态
     */
    getStatus() {
        return {
            isReady: this.isReady,
            signFunctionName: this.signFunctionName,
            targetUrl: this.targetUrl,
            timeout: this.timeout,
        };
    }

    /**
     * 销毁 Worker
     */
    async destroy() {
        this.isReady = false;
        // Page 由 BrowserPool 管理，这里不关闭
    }
}

module.exports = { SignWorker };
