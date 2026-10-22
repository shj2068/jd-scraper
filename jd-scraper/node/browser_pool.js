/**
 * Playwright 浏览器池管理模块
 * 
 * 管理多个 Playwright Page 实例，提供预热、健康检查、自动重启、
 * 信号量限流等功能。
 */

'use strict';

const { chromium } = require('playwright');
const { createStealthScript, getStealthLaunchArgs } = require('./stealth');
const { SignWorker } = require('./sign_worker');

class BrowserPool {
    /**
     * @param {Object} options - 配置选项
     * @param {number} options.poolSize - 池大小（Page 数量）
     * @param {boolean} options.headless - 是否无头模式
     * @param {number} options.warmupPages - 预热页面数
     * @param {string} options.targetUrl - 目标页面 URL
     * @param {number} options.healthCheckInterval - 健康检查间隔（ms）
     */
    constructor(options = {}) {
        this.poolSize = options.poolSize || 3;
        this.headless = options.headless !== false;
        this.warmupPages = options.warmupPages || 2;
        this.targetUrl = options.targetUrl || 'https://zhaoshang.jd.com/';
        this.healthCheckInterval = options.healthCheckInterval || 60000;

        this.browser = null;
        this.contexts = [];
        this.workers = [];
        this.availableWorkers = [];
        this.isInitialized = false;
        this.healthCheckTimer = null;

        // 信号量（并发控制）
        this.semaphore = {
            max: this.poolSize,
            current: 0,
            queue: [],
        };
    }

    /**
     * 初始化浏览器池
     */
    async init() {
        console.log(`初始化浏览器池: size=${this.poolSize}, headless=${this.headless}`);

        // 启动浏览器
        this.browser = await chromium.launch({
            headless: this.headless,
            args: getStealthLaunchArgs(),
        });

        // 创建 Page 实例
        for (let i = 0; i < this.poolSize; i++) {
            const context = await this.browser.newContext({
                userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport: { width: 1920, height: 1080 },
                locale: 'zh-CN',
                timezoneId: 'Asia/Shanghai',
                deviceScaleFactor: 1,
                isMobile: false,
                hasTouch: false,
            });

            const page = await context.newPage();

            // 创建 SignWorker
            const worker = new SignWorker(page, {
                targetUrl: this.targetUrl,
                timeout: 5000,
            });

            this.contexts.push(context);
            this.workers.push(worker);
            this.availableWorkers.push(worker);
        }

        // 预热
        await this._warmup();

        // 启动健康检查
        this._startHealthCheck();

        this.isInitialized = true;
        console.log(`浏览器池初始化完成: ${this.workers.length} 个 Worker`);
    }

    /**
     * 预热页面
     */
    async _warmup() {
        const warmupCount = Math.min(this.warmupPages, this.workers.length);
        console.log(`预热 ${warmupCount} 个页面...`);

        const warmupPromises = [];
        for (let i = 0; i < warmupCount; i++) {
            warmupPromises.push(this.workers[i].init());
        }

        await Promise.allSettled(warmupPromises);
        console.log('预热完成');
    }

    /**
     * 获取可用 Worker（信号量控制）
     */
    async acquire() {
        // 检查是否有可用 Worker
        if (this.availableWorkers.length > 0) {
            const worker = this.availableWorkers.pop();
            this.semaphore.current++;
            return worker;
        }

        // 等待可用
        return new Promise((resolve) => {
            this.semaphore.queue.push(resolve);
        });
    }

    /**
     * 释放 Worker
     */
    release(worker) {
        this.semaphore.current--;

        // 检查队列中是否有等待的请求
        if (this.semaphore.queue.length > 0) {
            const next = this.semaphore.queue.shift();
            this.availableWorkers.push(worker);
            next(worker);
        } else {
            this.availableWorkers.push(worker);
        }
    }

    /**
     * 执行签名（自动获取/释放 Worker）
     */
    async executeSign(params) {
        const worker = await this.acquire();

        try {
            if (!worker.isReady) {
                await worker.init();
            }
            const result = await worker.sign(params);
            return result;
        } finally {
            this.release(worker);
        }
    }

    /**
     * 启动健康检查
     */
    _startHealthCheck() {
        this.healthCheckTimer = setInterval(async () => {
            await this._checkHealth();
        }, this.healthCheckInterval);
    }

    /**
     * 执行健康检查
     */
    async _checkHealth() {
        for (const worker of this.workers) {
            try {
                // 简单检查页面是否存活
                const title = await worker.page.title();
                if (!title) {
                    console.warn('Worker 健康检查失败，尝试重启...');
                    await this._restartWorker(worker);
                }
            } catch (error) {
                console.error('Worker 健康检查异常:', error.message);
                await this._restartWorker(worker);
            }
        }
    }

    /**
     * 重启 Worker
     */
    async _restartWorker(worker) {
        try {
            worker.isReady = false;

            // 重新创建 Page
            const contextIndex = this.contexts.findIndex(
                (ctx) => ctx.pages().includes(worker.page)
            );

            if (contextIndex >= 0) {
                await this.contexts[contextIndex].close();
                const newContext = await this.browser.newContext({
                    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X)',
                    viewport: { width: 375, height: 812 },
                    locale: 'zh-CN',
                });
                const newPage = await newContext.newPage();
                worker.page = newPage;
                this.contexts[contextIndex] = newContext;
            }

            console.log('Worker 重启完成');
        } catch (error) {
            console.error('Worker 重启失败:', error.message);
        }
    }

    /**
     * 注入 Cookie 到所有 Worker
     */
    async injectCookies(cookies) {
        for (const worker of this.workers) {
            try {
                await worker.page.evaluate((cookieObj) => {
                    for (const [name, value] of Object.entries(cookieObj)) {
                        document.cookie = `${name}=${value}; path=/; domain=.jd.com`;
                    }
                }, cookies);
            } catch (error) {
                console.error('Cookie 注入失败:', error.message);
            }
        }
    }

    /**
     * 获取池状态
     */
    getStatus() {
        return {
            isInitialized: this.isInitialized,
            poolSize: this.poolSize,
            totalWorkers: this.workers.length,
            availableWorkers: this.availableWorkers.length,
            pendingRequests: this.semaphore.queue.length,
            workers: this.workers.map((w, i) => ({
                index: i,
                isReady: w.isReady,
                signFunction: w.signFunctionName,
            })),
        };
    }

    /**
     * 关闭浏览器池
     */
    async close() {
        console.log('关闭浏览器池...');

        if (this.healthCheckTimer) {
            clearInterval(this.healthCheckTimer);
        }

        for (const context of this.contexts) {
            try {
                await context.close();
            } catch (e) {}
        }

        if (this.browser) {
            await this.browser.close();
        }

        this.isInitialized = false;
        console.log('浏览器池已关闭');
    }
}

module.exports = { BrowserPool };
