/**
 * 提取的京东 h5st 签名函数
 * 
 * 从 zhaoshang.jd.com 页面逆向提取的 ParamsSign 类及其依赖
 * 版本: 5.3
 * 
 * 用法:
 *   const signer = new ParamsSign();
 *   const result = await signer.sign({ functionId, body, t, uuid });
 *   // result.h5st 即为签名值
 */

'use strict';

// 注意：这段代码依赖页面中已加载的全局变量
// 需要在浏览器上下文中执行，不能直接在 Node.js 中使用
// JSRPC 服务器通过 Playwright 在页面上下文中调用此函数

const H5ST_SIGN_SCRIPT = `
(function() {
  // 检查是否已经初始化
  if (window.__H5ST_SIGN_EXTRACTED__) {
    return window.__H5ST_SIGN_EXTRACTED__;
  }

  // ParamsSign 构造函数（版本 5.3）
  function ParamsSign(config) {
    var zb = fG;
    var fl = arguments.length > 0 && v.qyKlW(void 0, arguments[0]) ? arguments[0] : {};
    
    this._token = '';
    this._defaultToken = '';
    this._isNormal = true;
    this._appId = '';
    this._defaultAlgorithm = {
      'local_key_1': x2,
      'local_key_2': xu,
      'local_key_3': xA
    };
    this._algos = {
      'MD5': x2,
      'SHA256': xu,
      'HmacSHA256': xA,
      'HmacMD5': xd
    };
    this._version = zb(0x29f); // "5.3"
    this._fingerprint = '';
    
    fl = xt({}, ParamsSign.settings, fl);
    this._$icg(fl);
  }

  // 签名方法（异步）
  ParamsSign.prototype.sign = function(params) {
    return wS.resolve(this.signSync(params));
  };

  // 签名方法（同步）
  ParamsSign.prototype.signSync = function(params) {
    try {
      return this._$sdnmd(params);
    } catch (e) {
      this._onSign({'code': xx, 'message': 'sign error'});
      return params;
    }
  };

  // 导出到全局
  window.__H5ST_SIGN_EXTRACTED__ = {
    ParamsSign: ParamsSign,
    version: '5.3',
    ready: true
  };

  return window.__H5ST_SIGN_EXTRACTED__;
})();
`;

/**
 * 在 Playwright 页面上下文中执行签名
 * @param {Object} page - Playwright Page 对象
 * @param {Object} signParams - 签名参数
 * @returns {Promise<Object>} 签名结果（包含 h5st）
 */
async function executeSign(page, signParams) {
  // 确保签名脚本已注入
  await page.evaluate((script) => {
    if (!window.__H5ST_SIGN_EXTRACTED__) {
      eval(script);
    }
  }, H5ST_SIGN_SCRIPT);

  // 执行签名
  const result = await page.evaluate(async (params) => {
    if (!window.ParamsSign && window.__H5ST_SIGN_EXTRACTED__) {
      window.ParamsSign = window.__H5ST_SIGN_EXTRACTED__.ParamsSign;
    }
    
    if (!window.ParamsSign) {
      return { error: 'ParamsSign not available' };
    }

    try {
      const signer = new window.ParamsSign();
      const signResult = await signer.sign(params);
      return signResult;
    } catch (e) {
      return { error: e.message };
    }
  }, signParams);

  return result;
}

module.exports = { executeSign, H5ST_SIGN_SCRIPT };
