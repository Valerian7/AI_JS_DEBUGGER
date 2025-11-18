(function () {
    'use strict';

    let time = 0;

    // ==================== CryptoJS Hook ====================
    
    function hasEncryptProp(obj) {
        const requiredProps = ['ciphertext', 'key', 'iv', 'algorithm', 'mode', 'padding', 'blockSize', 'formatter'];
        if (!obj || typeof obj !== 'object') return false;
        for (const prop of requiredProps) {
            if (!(prop in obj)) return false;
        }
        return true;
    }

    function hasDecryptProp(obj) {
        const requiredProps = ['sigBytes', 'words'];
        if (!obj || typeof obj !== 'object') return false;
        for (const prop of requiredProps) {
            if (!(prop in obj)) return false;
        }
        return true;
    }

    function get_sigBytes(size) {
        switch (size) {
            case 8: return "64bits";
            case 16: return "128bits";
            case 24: return "192bits";
            case 32: return "256bits";
            default: return "未知";
        }
    }

    function hexToBase64(hex) {
        if (!hex) return '';
        try {
            const bytes = [];
            for (let i = 0; i < hex.length; i += 2) {
                bytes.push(parseInt(hex.substr(i, 2), 16));
            }
            return btoa(String.fromCharCode.apply(null, bytes));
        } catch (e) {
            return '';
        }
    }

    function wordsToHex(words, sigBytes) {
        if (!words || !Array.isArray(words)) return '';
        const hexChars = [];
        for (let i = 0; i < sigBytes; i++) {
            const byte = (words[i >>> 2] >>> (24 - (i % 4) * 8)) & 0xff;
            hexChars.push((byte >>> 4).toString(16));
            hexChars.push((byte & 0x0f).toString(16));
        }
        return hexChars.join('');
    }

    function formatKey(keyObj) {
        if (!keyObj) return { string: '', hex: '', base64: '' };
        
        let hexKey = '';
        let strKey = '';
        
        if (keyObj.toString && keyObj.toString() !== "[object Object]") {
            hexKey = keyObj.toString();
        } else if (keyObj.words && keyObj.sigBytes) {
            hexKey = wordsToHex(keyObj.words, keyObj.sigBytes);
        }
        
        const base64Key = hexToBase64(hexKey);
        
        try {
            strKey = decodeURIComponent(hexKey.replace(/[0-9a-f]{2}/g, '%$&'));
        } catch (e) {
            strKey = hexKey;
        }
        
        return {
            string: strKey,
            hex: hexKey,
            base64: base64Key
        };
    }

    let temp_apply = Function.prototype.apply;

    Function.prototype.apply = function () {
        // CryptoJS 对称加密
        if (arguments.length === 2 && arguments[0] && arguments[1] && typeof arguments[1] === 'object' && arguments[1].length === 1 && hasEncryptProp(arguments[1][0])) {
            if (Object.hasOwn(arguments[0], "$super") && Object.hasOwn(arguments[1], "callee")) {
                if (this.toString().indexOf('function()') !== -1 || /^\s*function(?:\s*\*)?\s+[A-Za-z_$][\w$]*\s*\([^)]*\)\s*\{/.test(this.toString()) || /^\s*function\s*\(\s*\)\s*\{/.test(this.toString())) {
                    
                    console.log("[debug] ========== CryptoJS 对称加密 ==========");
                    
                    const keyData = formatKey(arguments[1][0]["key"]);
                    console.log("[debug] Key (String):", keyData.string);
                    console.log("[debug] Key (Hex):", keyData.hex);
                    console.log("[debug] Key (Base64):", keyData.base64);

                    const iv = arguments[1][0]["iv"];
                    if (iv) {
                        const ivData = formatKey(iv);
                        console.log("[debug] IV (String):", ivData.string);
                        console.log("[debug] IV (Hex):", ivData.hex);
                        console.log("[debug] IV (Base64):", ivData.base64);
                    }

                    if (arguments[1][0]["key"] && Object.hasOwn(arguments[1][0]["key"], "sigBytes")) {
                        console.log("[debug] 密钥长度:", get_sigBytes(arguments[1][0]["key"]["sigBytes"]));
                    }

                    if (arguments[1][0]["mode"] && Object.hasOwn(arguments[1][0]["mode"], "Encryptor")) {
                        console.log("[debug] 运算模式:", arguments[1][0]["mode"]["Encryptor"]["processBlock"]);
                    }

                    if (arguments[1][0]["padding"]) {
                        console.log("[debug] 填充模式:", arguments[1][0]["padding"]);
                    }

                    let encrypt_text = arguments[0].$super.toString.call(arguments[1][0]);
                    if (encrypt_text !== "[object Object]") {
                        console.log("[debug] 密文:", encrypt_text);
                    }
                }
            }
        }
        // CryptoJS 对称解密
        else if (arguments.length === 2 && arguments[0] && arguments[1] && typeof arguments[1] === 'object' && arguments[1].length === 3 && hasDecryptProp(arguments[1][1])) {
            if (Object.hasOwn(arguments[0], "$super") && Object.hasOwn(arguments[1], "callee")) {
                if (this.toString().indexOf('function()') === -1 && arguments[1][0] === 2) {
                    
                    console.log("[debug] ========== CryptoJS 对称解密 ==========");
                    
                    const keyData = formatKey(arguments[1][1]);
                    console.log("[debug] Key (String):", keyData.string);
                    console.log("[debug] Key (Hex):", keyData.hex);
                    console.log("[debug] Key (Base64):", keyData.base64);

                    if (Object.hasOwn(arguments[1][2], "iv") && arguments[1][2]["iv"]) {
                        const ivData = formatKey(arguments[1][2]["iv"]);
                        console.log("[debug] IV (String):", ivData.string);
                        console.log("[debug] IV (Hex):", ivData.hex);
                        console.log("[debug] IV (Base64):", ivData.base64);
                    }

                    if (Object.hasOwn(arguments[1][2], "mode") && arguments[1][2]["mode"]) {
                        console.log("[debug] 运算模式:", arguments[1][2]["mode"]["Encryptor"]["processBlock"]);
                    }

                    if (Object.hasOwn(arguments[1][2], "padding") && arguments[1][2]["padding"]) {
                        console.log("[debug] 填充模式:", arguments[1][2]["padding"]);
                    }
                }
            }
        }
        // CryptoJS 哈希 / HMAC
        else if (arguments.length === 2 && arguments[0] && arguments[1] && typeof arguments[0] === 'object' && typeof arguments[1] === 'object') {
            if (arguments[0].__proto__ && Object.hasOwn(arguments[0].__proto__, "$super") && Object.hasOwn(arguments[0].__proto__, "_doFinalize") && arguments[0].__proto__.__proto__ && Object.hasOwn(arguments[0].__proto__.__proto__, "finalize")) {
                if (arguments[0].__proto__.__proto__.finalize.toString().indexOf('[debug]') === -1) {
                    let temp_finalize = arguments[0].__proto__.__proto__.finalize;

                    arguments[0].__proto__.__proto__.finalize = function () {
                        if (!(Object.hasOwn(this, "init"))) {
                            let hash = temp_finalize.call(this, ...arguments);
                            console.log("[debug] ========== CryptoJS 哈希/HMAC ==========");
                            console.log("[debug] 原始数据:", ...arguments);
                            console.log("[debug] 密文:", hash.toString());
                            console.log("[debug] 密文长度:", hash.toString().length);
                            return hash;
                        }
                        return temp_finalize.call(this, ...arguments)
                    }
                }
            }
        }
        return temp_apply.call(this, ...arguments);
    }

    // ==================== JSEncrypt RSA Hook ====================
    
    let c = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    
    function hexToBase64RSA(t) {
        let e, i, r = "";
        for (e = 0; e + 3 <= t.length; e += 3) {
            i = parseInt(t.substring(e, e + 3), 16);
            r += c.charAt(i >> 6) + c.charAt(63 & i);
        }
        for (e + 1 == t.length ? (i = parseInt(t.substring(e, e + 1), 16), r += c.charAt(i << 2)) : e + 2 == t.length && (i = parseInt(t.substring(e, e + 2), 16), r += c.charAt(i >> 2) + c.charAt((3 & i) << 4)); (3 & r.length) > 0;) {
            r += "=";
        }
        return r;
    }

    function hasRSAProp(obj) {
        const requiredProps = ['constructor', 'getPrivateBaseKey', 'getPrivateBaseKeyB64', 'getPrivateKey', 'getPublicBaseKey', 'getPublicBaseKeyB64', 'getPublicKey', 'parseKey', 'parsePropertiesFrom'];
        if (!obj || typeof obj !== 'object') return false;
        for (const prop of requiredProps) {
            if (!(prop in obj)) return false;
        }
        return true;
    }

    let temp_call = Function.prototype.call;

    Function.prototype.call = function () {
        if (arguments.length === 1 && arguments[0] && arguments[0].__proto__ && typeof arguments[0].__proto__ === 'object' && hasRSAProp(arguments[0].__proto__)) {
            if ("__proto__" in arguments[0].__proto__ && arguments[0].__proto__.__proto__ && Object.hasOwn(arguments[0].__proto__.__proto__, "encrypt") && Object.hasOwn(arguments[0].__proto__.__proto__, "decrypt")) {
                
                if (arguments[0].__proto__.__proto__.encrypt.toString().indexOf('[debug]') === -1) {
                    let temp_encrypt = arguments[0].__proto__.__proto__.encrypt;

                    arguments[0].__proto__.__proto__.encrypt = function () {
                        let encrypt_text = temp_encrypt.bind(this, ...arguments)();
                        
                        console.log("[debug] ========== RSA 加密 ==========");
                        console.log("[debug] 公钥:\n", this.getPublicKey());
                        console.log("[debug] 原始数据:", ...arguments);
                        console.log("[debug] 密文 (Hex):", encrypt_text);
                        console.log("[debug] 密文 (Base64):", hexToBase64RSA(encrypt_text));
                        
                        return encrypt_text;
                    }
                }

                if (arguments[0].__proto__.__proto__.decrypt.toString().indexOf('[debug]') === -1) {
                    let temp_decrypt = arguments[0].__proto__.__proto__.decrypt;

                    arguments[0].__proto__.__proto__.decrypt = function () {
                        let decrypt_text = temp_decrypt.bind(this, ...arguments)();
                        
                        console.log("[debug] ========== RSA 解密 ==========");
                        console.log("[debug] 私钥:\n", this.getPrivateKey());
                        console.log("[debug] 密文 (Base64):", hexToBase64RSA(...arguments));
                        console.log("[debug] 明文:", decrypt_text);
                        
                        return decrypt_text;
                    }
                }
            }
        }
        return temp_call.bind(this, ...arguments)();
    }

})();