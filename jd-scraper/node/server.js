/**
 * Express 签名服务主入口
 * 
 * 提供 HTTP API 接口，接收 Python 客户端的签名请求，
 * 通过浏览器池生成 h5st 签名。
 */

'use strict';

const express = require('express');
const rateLimit = require('express-rate-limit');
const { BrowserPool } = require('./browser_pool');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(express.json({ limit: '1mb' }));

// 请求限流
const limiter = rateLimit({
    windowMs: 60 * 1000, // 1 分钟
    max: 100, // 每分钟最多 100 请求
    message: { code: -1, error: '请求过于频繁，请稍后再试' },
});
app.use('/sign', limiter);

// 浏览器池实例
let browserPool = null;

/**
 * POST /sign - h5st 签名接口
 */
app.post('/sign', async (req, res) => {
    try {
        const { functionId, body, t, uuid } = req.body;

        // 参数校验
        if (!functionId) {
            return res.json({ code: -1, error: '缺少 functionId 参数' });
        }
        if (!uuid) {
            return res.json({ code: -1, error: '缺少 uuid 参数' });
        }

        if (!browserPool || !browserPool.isInitialized) {
            return res.json({ code: -1, error: '签名服务未初始化' });
        }

        // 执行签名
        const result = await browserPool.executeSign({
            functionId,
            body: body || '',
            t: t || String(Date.now()),
            uuid,
        });

        res.json(result);
    } catch (error) {
        console.error('签名接口错误:', error);
        res.json({ code: -1, error: error.message });
    }
});

/**
 * POST /sign/batch - 批量签名接口
 */
app.post('/sign/batch', async (req, res) => {
    try {
        const { requests } = req.body;

        if (!Array.isArray(requests) || requests.length === 0) {
            return res.json({ code: -1, error: '缺少 requests 数组' });
        }

        if (!browserPool || !browserPool.isInitialized) {
            return res.json({ code: -1, error: '签名服务未初始化' });
        }

        // 并发执行签名
        const promises = requests.map((req) =>
            browserPool.executeSign({
                functionId: req.functionId,
                body: req.body || '',
                t: req.t || String(Date.now()),
                uuid: req.uuid,
            })
        );

        const results = await Promise.allSettled(promises);
        const responses = results.map((r) => {
            if (r.status === 'fulfilled') {
                return r.value;
            }
            return { code: -1, error: r.reason.message };
        });

        res.json({ code: 0, results: responses });
    } catch (error) {
        console.error('批量签名错误:', error);
        res.json({ code: -1, error: error.message });
    }
});

/**
 * GET /health - 健康检查接口
 */
app.get('/health', (req, res) => {
    const status = browserPool ? browserPool.getStatus() : null;

    res.json({
        status: status && status.isInitialized ? 'ok' : 'unavailable',
        timestamp: Date.now(),
        pool: status,
    });
});

/**
 * POST /cookie/inject - Cookie 注入接口
 */
app.post('/cookie/inject', async (req, res) => {
    try {
        const { cookies } = req.body;

        if (!cookies || typeof cookies !== 'object') {
            return res.json({ code: -1, error: '缺少 cookies 参数' });
        }

        if (!browserPool || !browserPool.isInitialized) {
            return res.json({ code: -1, error: '签名服务未初始化' });
        }

        await browserPool.injectCookies(cookies);
        res.json({ code: 0, message: 'Cookie 注入成功' });
    } catch (error) {
        console.error('Cookie 注入错误:', error);
        res.json({ code: -1, error: error.message });
    }
});

/**
 * GET /status - 服务状态接口
 */
app.get('/status', (req, res) => {
    res.json({
        service: 'jd-scraper-sign-server',
        version: '1.0.0',
        uptime: process.uptime(),
        pool: browserPool ? browserPool.getStatus() : null,
    });
});

/**
 * 启动服务
 */
async function startServer() {
    try {
        // 初始化浏览器池
        browserPool = new BrowserPool({
            poolSize: parseInt(process.env.POOL_SIZE) || 3,
            headless: process.env.HEADLESS !== 'false',
            warmupPages: parseInt(process.env.WARMUP_PAGES) || 2,
            targetUrl: process.env.TARGET_URL || 'https://zhaoshang.jd.com/',
        });

        await browserPool.init();

        // 启动 HTTP 服务
        app.listen(PORT, () => {
            console.log(`========================================`);
            console.log(`  京东 h5st 签名服务已启动`);
            console.log(`  端口: ${PORT}`);
            console.log(`  浏览器池: ${browserPool.poolSize} 个 Worker`);
            console.log(`  模式: ${browserPool.headless ? '无头' : '有头'}`);
            console.log(`========================================`);
            console.log(`  签名接口: POST http://localhost:${PORT}/sign`);
            console.log(`  批量接口: POST http://localhost:${PORT}/sign/batch`);
            console.log(`  健康检查: GET  http://localhost:${PORT}/health`);
            console.log(`========================================`);
        });
    } catch (error) {
        console.error('服务启动失败:', error);
        process.exit(1);
    }
}

/**
 * 优雅关闭
 */
async function gracefulShutdown(signal) {
    console.log(`\n收到 ${signal} 信号，正在关闭服务...`);

    if (browserPool) {
        await browserPool.close();
    }

    process.exit(0);
}

process.on('SIGINT', () => gracefulShutdown('SIGINT'));
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));

// 未捕获异常处理
process.on('uncaughtException', (error) => {
    console.error('未捕获异常:', error);
});

process.on('unhandledRejection', (reason) => {
    console.error('未处理的 Promise 拒绝:', reason);
});

// 启动服务
if (require.main === module) {
    startServer();
}

module.exports = { app, startServer };
