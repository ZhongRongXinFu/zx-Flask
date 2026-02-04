# 微信消息加密解密实现文档

## 概述

已实现微信消息的**安全模式**加密/解密功能，支持：
1. ✅ msg_signature签名验证
2. ✅ AES-256-CBC解密接收消息
3. ✅ AES-256-CBC加密回包消息
4. ✅ 回包签名生成

## 文件结构

```
utils/wechat_crypt.py       # 加密解密工具类
pages/wechat.py             # Webhook路由实现  
settings.py                 # 配置文件
```

## 核心类：WXBizMsgCrypt

位置：`utils/wechat_crypt.py`

### 初始化

```python
from utils.wechat_crypt import WXBizMsgCrypt

crypt = WXBizMsgCrypt(
    token="你的Token",
    encoding_aes_key="你的43位EncodingAESKey",
    appid="你的小程序AppID"
)
```

### 主要方法

#### 1. verify_signature() - 验证签名

```python
is_valid = crypt.verify_signature(
    signature_str=msg_signature,  # URL中的msg_signature
    timestamp=timestamp,           # URL中的timestamp
    nonce=nonce,                   # URL中的nonce
    encrypt_msg=encrypt            # POST body中的Encrypt字段
)
```

**验证流程：**
1. 将token、timestamp、nonce、encrypt四个参数字典序排序
2. 拼接排序后的字符串
3. SHA1计算签名
4. 与URL中的msg_signature对比

#### 2. decrypt() - 解密消息

```python
success, decrypted_msg, from_appid = crypt.decrypt(encrypt_msg)

if success:
    msg_data = json.loads(decrypted_msg)
    # 处理消息
```

**解密流程：**
1. Base64解码密文
2. AES-256-CBC解密（IV使用AESKey前16字节）
3. 去除PKCS#7填充
4. 解析：random(16B) + msg_len(4B) + msg + appid
5. 验证appid是否匹配

#### 3. encrypt() - 加密回包

```python
reply_msg = '{"demo_resp":"good luck"}'
encrypted = crypt.encrypt(reply_msg)
```

**加密流程：**
1. 生成16字节随机字符串
2. 构造：random(16B) + msg_len(4B) + msg + appid
3. PKCS#7填充到32字节整数倍
4. AES-256-CBC加密
5. Base64编码

#### 4. generate_signature() - 生成回包签名

```python
signature = crypt.generate_signature(
    timestamp=str(int(time.time())),
    nonce=nonce,
    encrypt_msg=encrypted
)
```

## Webhook接口实现

### 路由：POST /wechat/webhook/

位置：`pages/wechat.py`

### 请求示例

**URL：**
```
POST /wechat/webhook/?signature=xxx&timestamp=1714112445&nonce=415670741&openid=xxx&encrypt_type=aes&msg_signature=046e02f8204d34f8ba5fa3b1db94908f3df2e9b3
```

**Body (JSON)：**
```json
{
    "ToUserName": "gh_97417a04a28d",
    "Encrypt": "+qdx1OKCy+5JPCBFWw70tm0fJGb2Jmeia4FCB7kao+/Q5c/ohsOzQHi8khUOb05JCpj0JB4RvQMkUyus8TPxLKJGQqcvZqzDpVzazhZv6JsXUnnR8XGT740XgXZUXQ7vJVnAG+tE8NUd4yFyjPy7GgiaviNrlCTj+l5kdfMuFUPpRSrfMZuMcp3Fn2Pede2IuQrKEYwKSqFIZoNqJ4M8EajAsjLY2km32IIjdf8YL/P50F7mStwntrA2cPDrM1kb6mOcfBgRtWygb3VIYnSeOBrebufAlr7F9mFUPAJGj04="
}
```

### 处理流程

```python
# 1. 验证msg_signature
if not crypt.verify_signature(msg_signature, timestamp, nonce, encrypt_msg):
    return 401  # 签名验证失败

# 2. 解密消息
success, decrypted_msg, from_appid = crypt.decrypt(encrypt_msg)
msg_data = json.loads(decrypted_msg)

# 3. 处理业务逻辑
if msg_data['MsgType'] == 'event':
    if msg_data['Event'] == 'xpay_goods_deliver_notify':
        # 处理支付回调
        pass

# 4. 构造回包
reply_msg = "success"  # 或者 JSON字符串

# 5. 加密回包
encrypted_reply = crypt.encrypt(reply_msg)

# 6. 生成回包签名
reply_timestamp = int(time.time())
reply_signature = crypt.generate_signature(reply_timestamp, nonce, encrypted_reply)

# 7. 返回加密回包
return {
    "Encrypt": encrypted_reply,
    "MsgSignature": reply_signature,
    "TimeStamp": reply_timestamp,
    "Nonce": nonce
}
```

### 响应示例

```json
{
    "Encrypt": "ELGduP2YcVatjqIS+eZbp80MNLoAUWvzzyJxgGzxZO/5sAvd070Bs6qrLARC9nVHm48Y4hyRbtzve1L32tmxSQ==",
    "MsgSignature": "1b9339964ed2e271e7c7b6ff2b0ef902fc94dea1",
    "TimeStamp": 1713424427,
    "Nonce": "415670741"
}
```

## 配置说明

### settings.py

```python
WX_APP_ID = 'wx276d3b776e47c682'  # 小程序AppID
WX_MIDAS_TOKEN = 'WDMNEYNnaLIEDABSBIDYNASODIBQWUEQ'  # Token
WX_MIDAS_ENCODING_AES_KEY = 'LvIaGOIjqberGcsvY7r4dWdGWIC0GWjZMhexfoR5v1G'  # 43位EncodingAESKey
```

**注意：**
- Token和EncodingAESKey必须与微信公众平台配置一致
- EncodingAESKey为43位字符串
- 这些配置在微信公众平台"开发设置"中获取

## 测试方法

### 方法1：使用Python脚本测试

```bash
cd /Users/ksuserkqy/Desktop/zhongxin/flask
.venv/bin/python test_crypt_simple.py
```

### 方法2：使用curl测试webhook

```bash
curl -X POST "http://localhost:5000/wechat/webhook/?msg_signature=046e02f8204d34f8ba5fa3b1db94908f3df2e9b3&timestamp=1714112445&nonce=415670741&openid=test" \
  -H "Content-Type: application/json" \
  -d '{
    "ToUserName": "gh_97417a04a28d",
    "Encrypt": "+qdx1OKCy+5JPCBFWw70tm0fJGb2Jmeia4FCB7kao+/Q5c/ohsOzQHi8khUOb05JCpj0JB4RvQMkUyus8TPxLKJGQqcvZqzDpVzazhZv6JsXUnnR8XGT740XgXZUXQ7vJVnAG+tE8NUd4yFyjPy7GgiaviNrlCTj+l5kdfMuFUPpRSrfMZuMcp3Fn2Pede2IuQrKEYwKSqFIZoNqJ4M8EajAsjLY2km32IIjdf8YL/P50F7mStwntrA2cPDrM1kb6mOcfBgRtWygb3VIYnSeOBrebufAlr7F9mFUPAJGj04="
  }'
```

## 依赖包

需要安装 `pycryptodome` 库：

```bash
pip install pycryptodome
```

已添加到项目依赖中。

## 常见问题

### Q1: 签名验证失败

**原因：**
- Token配置错误
- 参数排序错误（必须字典序）
- Encrypt字段获取错误

**解决：**
- 检查settings.py中的WX_MIDAS_TOKEN
- 确保使用msg_signature而不是signature验证
- 确保Encrypt字段完整无误

### Q2: 解密失败

**原因：**
- EncodingAESKey配置错误
- Encrypt字段被修改
- Base64解码失败

**解决：**
- 检查settings.py中的WX_MIDAS_ENCODING_AES_KEY（43位）
- 确保Encrypt字段原封不动传递
- 检查是否有编码问题

### Q3: AppID不匹配

**原因：**
- settings.py中的WX_APP_ID与消息中的appid不一致

**解决：**
- 更新settings.py中的WX_APP_ID为正确值
- 确保是接收消息的小程序AppID

## 技术细节

### AES加密参数

- **模式：** CBC
- **密钥长度：** 32字节（256位）
- **IV：** AESKey的前16字节
- **填充：** PKCS#7

### 数据格式

**加密前：**
```
random(16字节) + msg_len(4字节网络字节序) + msg + appid
```

**加密后：**
```
Base64编码(AES加密后的数据)
```

### 签名算法

```
SHA1(sorted([token, timestamp, nonce, encrypt]).join())
```

## 扩展业务逻辑

在 `wechat_webhook_handle()` 函数中添加你的业务处理：

```python
# 4. 处理不同类型的消息
msg_type = msg_data.get("MsgType")
event = msg_data.get("Event")

if msg_type == "event":
    if event == "xpay_goods_deliver_notify":
        # 米大师支付回调
        # TODO: 调用支付处理逻辑
        order_id = msg_data.get("order_id")
        # 处理订单，增加用户额度等
        
    elif event == "user_enter_tempsession":
        # 用户进入客服会话
        pass
```

## 参考文档

- [微信消息加密解密技术方案](https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Message_encryption_and_decryption_instructions.html)
- [米大师支付回调](https://developers.weixin.qq.com/minigame/dev/api-backend/midas-payment/midas-payment.presentCurrency.html)
