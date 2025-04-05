# 提示词模板文件
# 本文件集中存储所有AI模型使用的提示词模板，便于统一管理和更新

# 调试指令分析提示词 - 用于决定下一步调试操作（step_into/step_out/step_over）
DEBUG_INSTRUCTION_PROMPT = '''
任务：根据JavaScript调试信息分析加密相关代码并决定最优调试策略。

分析重点：
1. 加密函数识别：
   - 函数名包含encrypt/decrypt/AES/RSA/DES/MD5/SHA/Hash/Crypto/签名/code等关键词
   - JavaScript特有加密：btoa/atob(Base64)、TextEncoder/TextDecoder、crypto.subtle等Web API
   - 位运算加密：XOR(^)、位移(<<,>>)、按位与(&)、按位或(|)等操作
2. 可疑函数调用：
   - 网络请求相关：fetch/XMLHttpRequest/axios/$.ajax/sendData*/getToken*/getSign*/request*
   - 数据处理相关：JSON.parse/stringify、URLSearchParams、FormData操作
3. 加密库识别：
   - 主流库：CryptoJS/WebCrypto/forge/jsencrypt/crypto-js/sjcl/noble-*
   - 自定义库：检测_加密函数命名模式、特定算法实现特征
4. 数据转换操作：
   - 编码转换：Base64/HEX/UTF-8/encodeURIComponent/escape
   - 字符串操作：toString/fromCharCode/charCodeAt/padStart/padEnd/split/join
   - 数组操作：TypedArray(Uint8Array等)、Array.from、map/reduce用于字节处理
5. 混淆代码识别：
   - 动态执行：eval/Function构造函数/setTimeout+字符串/new Function()
   - 字符串拼接：大量的字符串拼接、字符编码转换、数组join操作
   - 控制流扁平化：大型switch-case结构、状态机模式、大量条件判断
   - 变量混淆：单字符变量、数字变量名、无意义变量名
6. 可疑参数：IV/key/salt/mode/padding/secret/token/sign/signature等加密参数

精确决策规则：
- 【step_into】发现首次出现的加密相关函数调用时，进入该函数内部
- 【step_over】已经处于加密函数内部时，对非核心操作进行单步跳过
- 【step_into】遇到eval、Function构造函数、动态执行代码时，尝试进入查看实际执行内容
- 【step_out】深入3层以上的内部库函数实现或重复的循环操作时，跳出当前函数
- 【step_out】连续3次在相同位置或相似上下文中执行或"作用域中未找到相关变量"时，避免调试陷入循环
- 【step_over】遇到大量混淆代码或控制流扁平化结构时，优先跳过复杂逻辑直到返回有意义结果
输出格式：仅返回单一JSON对象，三个字段中只有一个为true
{
  "step_into": false,
  "step_over": false,
  "step_out": false
}
'''

# 调试日志分析提示词 - 用于分析完整的调试日志
DEBUGGER_ANALYZE_PROMPT = '''
这是我的JavaScript调试信息，请帮我分析：

1. 加解密方法识别：
   - 识别所有加密/解密函数及其调用链
   - 分析加密算法类型（对称/非对称/哈希等）
   - 识别自定义加密算法和混淆技术

2. 密钥提取：
   - 提取所有加密密钥、IV、salt等参数
   - 分析密钥生成/派生逻辑
   - 识别密钥存储位置（本地存储/Cookie/内存）

3. 关键代码分析：
   - 提取核心加解密逻辑，简化并注释
   - 分析混淆代码的实际功能
   - 识别动态执行代码（eval/Function）的实际内容

4. 编写mitmproxy脚本：
   - 实现请求/响应数据的解密和加密
   - 处理特殊头部和参数
   - 确保脚本简洁高效

请保持分析简洁，不需要加固建议，专注于核心加解密逻辑和mitmproxy脚本实现。
'''

# 系统角色提示词 - 用于设置AI的角色定位
SYSTEM_ROLE_PROMPT = '''
你是一个专业的JavaScript代码分析专家，擅长分析加密算法和网络请求
'''