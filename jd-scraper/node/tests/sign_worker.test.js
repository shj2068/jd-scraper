/**
 * sign_worker.js 单元测试
 */
'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { SignWorker } = require('../sign_worker');

describe('SignWorker', () => {
    it('构造函数接受 page 和 options', () => {
        const mockPage = { addInitScript: async () => {}, goto: async () => {} };
        const worker = new SignWorker(mockPage, {
            timeout: 3000,
            targetUrl: 'https://example.com',
        });
        assert.equal(worker.timeout, 3000);
        assert.equal(worker.targetUrl, 'https://example.com');
        assert.equal(worker.isReady, false);
    });

    it('使用默认超时', () => {
        const mockPage = {};
        const worker = new SignWorker(mockPage);
        assert.equal(worker.timeout, 5000);
    });

    it('使用默认目标 URL', () => {
        const mockPage = {};
        const worker = new SignWorker(mockPage);
        assert.equal(worker.targetUrl, 'https://zhaoshang.jd.com/');
    });

    it('signFunctionName 默认为 null', () => {
        const mockPage = {};
        const worker = new SignWorker(mockPage);
        assert.equal(worker.signFunctionName, null);
    });

    it('可指定签名函数名', () => {
        const mockPage = {};
        const worker = new SignWorker(mockPage, {
            signFunctionName: 'getH5st',
        });
        assert.equal(worker.signFunctionName, 'getH5st');
    });
});
