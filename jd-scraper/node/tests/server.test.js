/**
 * server.js API 端点测试
 * 使用 supertest 风格的手动 HTTP 测试（避免额外依赖）
 */
'use strict';

const { describe, it, before, after, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');

// 导入 Express app（不启动服务器）
const { app } = require('../server');

let server;
let baseUrl;

function request(method, path, body) {
    return new Promise((resolve, reject) => {
        const url = new URL(path, baseUrl);
        const options = {
            hostname: url.hostname,
            port: url.port,
            path: url.pathname,
            method,
            headers: { 'Content-Type': 'application/json' },
        };

        const req = http.request(options, (res) => {
            let data = '';
            res.on('data', (chunk) => (data += chunk));
            res.on('end', () => {
                try {
                    resolve({ status: res.statusCode, body: JSON.parse(data) });
                } catch {
                    resolve({ status: res.statusCode, body: data });
                }
            });
        });

        req.on('error', reject);
        if (body) req.write(JSON.stringify(body));
        req.end();
    });
}

before(async () => {
    server = app.listen(0);
    const addr = server.address();
    baseUrl = `http://127.0.0.1:${addr.port}`;
});

after(async () => {
    if (server) server.close();
});

describe('POST /sign', () => {
    it('缺少 functionId 返回错误', async () => {
        const res = await request('POST', '/sign', { uuid: 'test-uuid' });
        assert.equal(res.body.code, -1);
        assert.ok(res.body.error.includes('functionId'));
    });

    it('缺少 uuid 返回错误', async () => {
        const res = await request('POST', '/sign', { functionId: 'test' });
        assert.equal(res.body.code, -1);
        assert.ok(res.body.error.includes('uuid'));
    });

    it('未初始化时返回错误', async () => {
        const res = await request('POST', '/sign', {
            functionId: 'test',
            uuid: 'test-uuid',
        });
        assert.equal(res.body.code, -1);
        assert.ok(res.body.error.includes('未初始化'));
    });
});

describe('POST /sign/batch', () => {
    it('空数组返回错误', async () => {
        const res = await request('POST', '/sign/batch', { requests: [] });
        assert.equal(res.body.code, -1);
    });

    it('非数组返回错误', async () => {
        const res = await request('POST', '/sign/batch', { requests: 'not-array' });
        assert.equal(res.body.code, -1);
    });

    it('未初始化时返回错误', async () => {
        const res = await request('POST', '/sign/batch', {
            requests: [{ functionId: 'test', uuid: 'u1' }],
        });
        assert.equal(res.body.code, -1);
    });
});

describe('GET /health', () => {
    it('返回健康状态', async () => {
        const res = await request('GET', '/health');
        assert.ok(res.body.timestamp);
        assert.ok(res.body.status === 'ok' || res.body.status === 'unavailable');
    });
});

describe('GET /status', () => {
    it('返回服务信息', async () => {
        const res = await request('GET', '/status');
        assert.equal(res.body.service, 'jd-scraper-sign-server');
        assert.ok(res.body.version);
        assert.ok(typeof res.body.uptime === 'number');
    });
});

describe('POST /cookie/inject', () => {
    it('缺少 cookies 返回错误', async () => {
        const res = await request('POST', '/cookie/inject', {});
        assert.equal(res.body.code, -1);
    });

    it('未初始化时返回错误', async () => {
        const res = await request('POST', '/cookie/inject', {
            cookies: { test: 'value' },
        });
        assert.equal(res.body.code, -1);
    });
});
