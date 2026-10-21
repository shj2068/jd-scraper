/**
 * stealth.js 单元测试
 */
'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { createStealthScript, getStealthLaunchArgs } = require('../stealth');

describe('createStealthScript', () => {
    it('返回一个函数', () => {
        const script = createStealthScript();
        assert.equal(typeof script, 'function');
    });

    it('使用默认参数', () => {
        const script = createStealthScript();
        const source = script.toString();
        assert.ok(source.includes('navigator'));
        assert.ok(source.includes('webdriver'));
    });

    it('接受自定义平台参数', () => {
        const script = createStealthScript({
            platform: 'MacIntel',
            language: 'en-US',
            languages: ['en-US', 'en'],
            hardwareConcurrency: 4,
        });
        assert.equal(typeof script, 'function');
    });

    it('接受自定义 WebGL 参数', () => {
        const script = createStealthScript({
            webglVendor: 'Apple',
            webglRenderer: 'Apple M1',
        });
        assert.equal(typeof script, 'function');
    });

    it('生成的脚本包含 Canvas 反检测', () => {
        const script = createStealthScript();
        const source = script.toString();
        assert.ok(source.includes('canvas') || source.includes('Canvas'));
    });

    it('生成的脚本包含 WebGL 反检测', () => {
        const script = createStealthScript();
        const source = script.toString();
        assert.ok(source.includes('webgl') || source.includes('WebGL'));
    });

    it('生成的脚本包含 AudioContext 反检测', () => {
        const script = createStealthScript();
        const source = script.toString();
        assert.ok(source.includes('AudioContext') || source.includes('audio'));
    });
});

describe('getStealthLaunchArgs', () => {
    it('返回数组', () => {
        const args = getStealthLaunchArgs();
        assert.ok(Array.isArray(args));
    });

    it('包含 AutomationControlled 禁用', () => {
        const args = getStealthLaunchArgs();
        const hasAutomation = args.some(a => a.includes('AutomationControlled'));
        assert.ok(hasAutomation);
    });

    it('包含 no-sandbox', () => {
        const args = getStealthLaunchArgs();
        assert.ok(args.includes('--no-sandbox'));
    });

    it('包含语言设置', () => {
        const args = getStealthLaunchArgs();
        const hasLang = args.some(a => a.includes('--lang='));
        assert.ok(hasLang);
    });

    it('所有参数以 -- 开头', () => {
        const args = getStealthLaunchArgs();
        for (const arg of args) {
            assert.ok(arg.startsWith('--'), `参数 "${arg}" 不以 -- 开头`);
        }
    });
});
