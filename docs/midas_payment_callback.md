# 米大师支付回调处理文档

## 概述

已实现完整的米大师支付回调处理机制，自动处理以下流程：
1. 验证消息签名和加密
2. 解密消息内容
3. 查询订单信息
4. 更新订单状态
5. 增加用户AI额度
6. 记录额度变动日志

## 回调流程

### 整体流程图

```
微信米大师支付系统
        ↓
用户完成支付
        ↓
米大师服务器推送 xpay_goods_deliver_notify
        ↓
POST /wechat/webhook/
        ↓
验证msg_signature ✓
        ↓
解密Encrypt消息 ✓
        ↓
extract OrderId, Amount等
        ↓
handle_midas_payment_callback()
        ↓
查询recharge_order表
        ↓
验证订单状态（必须为0-待支付）
        ↓
更新订单状态为2（支付中）
        ↓
增加user.quota
        ↓
记录ai_quota_log
        ↓
更新订单状态为3（已完成）
        ↓
返回"success"给微信
        ↓
用户立即获得AI额度
```

## 函数实现

### handle_midas_payment_callback()

位置：`pages/wechat.py`

```python
def handle_midas_payment_callback(
    order_id: str,      # 米大师订单ID
    openid: str,        # 用户openid
    amount: int,        # 支付金额（分）
    currency: str,      # 货币类型（CNY）
    msg_data: dict      # 完整消息数据
) -> bool:             # 返回是否成功
```

### 处理步骤

#### 1. 查询订单信息

```sql
SELECT * FROM recharge_order 
WHERE wx_order_id = ? OR order_no = ?
```

验证以下信息：
- 订单是否存在
- 订单状态是否为0（待支付）
- 用户ID、UUID、额度数量等

#### 2. 更新订单状态为"支付中"（status=2）

```sql
UPDATE recharge_order 
SET status = 2, wx_transaction_id = ?, pay_time = NOW()
WHERE id = ?
```

#### 3. 增加用户AI额度

```sql
UPDATE user 
SET quota = quota + ? 
WHERE id = ?
```

记录变更前后的额度值用于日志。

#### 4. 记录额度变动日志

调用 `log_quota_change()` 函数：
```python
log_quota_change(
    user_id=user_id,
    uuid=user_uuid,
    change_type='purchase',        # 购买充值
    change_amount=quota_amount,    # 增加的额度
    quota_before=old_quota,        # 变更前
    quota_after=new_quota,         # 变更后
    related_id=order_id,           # 订单ID
    remark='米大师充值订单: XXX'
)
```

#### 5. 更新订单状态为"已完成"（status=3）

```sql
UPDATE recharge_order 
SET status = 3, complete_time = NOW()
WHERE id = ?
```

#### 6. 返回成功

webhook 返回 `"success"` 给微信，确认发货完成。

## 数据库表

### recharge_order 表

订单表，字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| order_no | VARCHAR(64) | 订单号 |
| user_id | INT | 用户ID |
| uuid | VARCHAR(64) | 用户UUID |
| package_id | INT | 套餐ID |
| quota_amount | INT | 购买额度 |
| price | INT | 订单金额（分） |
| wx_order_id | VARCHAR(128) | 微信订单号 |
| wx_transaction_id | VARCHAR(128) | 微信交易号 |
| **status** | TINYINT | **订单状态** |
| pay_time | TIMESTAMP | 支付时间 |
| complete_time | TIMESTAMP | 完成时间 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**订单状态码：**
- 0 - 待支付
- 1 - 支付中
- **2 - 已支付**（回调时更新）
- **3 - 已完成**（额度到账）
- 4 - 已取消
- 5 - 已退款

### user 表

用户表，关键字段：

| 字段 | 说明 |
|------|------|
| id | 用户ID |
| uuid | 用户UUID |
| **quota** | **AI额度余额** |

### ai_quota_log 表

额度变动日志表：

| 字段 | 说明 |
|------|------|
| user_id | 用户ID |
| uuid | 用户UUID |
| change_type | 变动类型 |
| change_amount | 变动数量 |
| quota_before | 变动前 |
| quota_after | 变动后 |
| related_id | 关联ID（订单号） |
| remark | 备注 |

## 消息数据格式

### xpay_goods_deliver_notify 消息示例

```json
{
  "ToUserName": "gh_487c3ab1de4d",
  "FromUserName": "ozNfp4jF3oJ3oqCMDFT8mdfc4I_k",
  "CreateTime": 1770211921,
  "MsgType": "event",
  "Event": "xpay_goods_deliver_notify",
  "OrderId": "1770211921000001",
  "Amount": 990,
  "Currency": "CNY",
  "TransactionId": "wx20240204100000abcdefgh",
  "Status": 0,
  "ProductId": 1,
  "PurchaseQuantity": 1,
  "PurchaseCoinQuantity": 0
}
```

**关键字段：**
- `OrderId` - 米大师订单ID
- `Amount` - 支付金额（分）
- `Currency` - 货币类型
- `FromUserName` - 用户openid
- `TransactionId` - 微信交易号
- `CreateTime` - 支付时间

## 错误处理

### 异常情况

| 情况 | 处理方式 | 结果 |
|------|----------|------|
| 订单不存在 | 返回False，记录日志 | 支付失败，用户无法获得额度 |
| 订单已处理 | 返回True（幂等性） | 避免重复处理 |
| 数据库错误 | 捕获异常，返回False | 事务回滚，保持一致性 |
| 其他异常 | 捕获异常，打印堆栈 | 调试和日志记录 |

### 重试机制

微信服务器会在以下情况下重试推送：
- 服务器返回非200状态码
- 服务器超时（默认5秒）
- 服务器异常

**重试间隔：** 30秒、60秒、120秒...（最多重试3次）

## 日志输出

系统自动输出处理过程日志：

```
处理米大师支付回调...
支付回调数据: {...}
订单状态已更新为支付中: 1770211921000001
用户额度已更新: 123, 76 → 86
额度日志已记录: {'code': 0, ...}
订单处理完成: 1770211921000001
```

## 配置需求

### settings.py

```python
# 数据库配置（必需）
DB_HOST = "localhost"
DB_USER = "api"
DB_PASSWORD = "xxx"
DB_DATABASE = "zhongrong"
DB_PORT = 3306

# 微信配置（必需）
WX_APP_ID = 'wx276d3b776e47c682'
WX_MIDAS_TOKEN = 'xxx'
WX_ENCODINGAESKEY = 'xxx'
```

### 数据库初始化

执行以下SQL创建所需的表：

```sql
-- 用户表（如果不存在）
CREATE TABLE IF NOT EXISTS user (
  id INT AUTO_INCREMENT PRIMARY KEY,
  uuid VARCHAR(64) NOT NULL UNIQUE,
  quota INT DEFAULT 0,
  ...
);

-- 订单表
CREATE TABLE IF NOT EXISTS recharge_order (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_no VARCHAR(64) NOT NULL UNIQUE,
  user_id INT NOT NULL,
  uuid VARCHAR(64) NOT NULL,
  package_id INT NOT NULL,
  quota_amount INT NOT NULL,
  price INT NOT NULL,
  wx_order_id VARCHAR(128),
  wx_transaction_id VARCHAR(128),
  status TINYINT DEFAULT 0,
  pay_time TIMESTAMP NULL,
  complete_time TIMESTAMP NULL,
  user_ip VARCHAR(50),
  remark TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY user_id (user_id),
  KEY uuid (uuid),
  KEY status (status)
);

-- 额度日志表
CREATE TABLE IF NOT EXISTS ai_quota_log (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  uuid VARCHAR(64) NOT NULL,
  change_type VARCHAR(20) NOT NULL,
  change_amount INT NOT NULL,
  quota_before INT NOT NULL,
  quota_after INT NOT NULL,
  related_id VARCHAR(128),
  remark TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  KEY user_id (user_id),
  KEY change_type (change_type)
);
```

## 测试方法

### 1. 使用微信调试工具

通过微信公众平台的"消息推送请求调试"工具：

1. 选择事件类型：`xpay_goods_deliver_notify`
2. 输入必要参数
3. 点击"推送请求"
4. 查看返回结果

### 2. 模拟调用

```bash
# 1. 先创建一个待支付订单
POST /payment/midas/recharge/create/
Body: {
  "uuid": "user-uuid",
  "package_id": 1,
  "openid": "user-openid"
}
# 返回: {"order_no": "RO1770211921000abc", ...}

# 2. 模拟支付回调
POST /wechat/webhook/?msg_signature=xxx&timestamp=1770211921&nonce=255180634&openid=ozNfp4jF3oJ3oqCMDFT8mdfc4I_k

Body: {
  "ToUserName": "gh_487c3ab1de4d",
  "Encrypt": "cvuYCzdkS9k+..." // 加密的消息
}
```

### 3. 验证结果

检查以下内容：

```sql
-- 检查订单状态
SELECT * FROM recharge_order WHERE order_no = 'RO1770211921000abc';
-- status 应该为 3（已完成）

-- 检查用户额度
SELECT quota FROM user WHERE id = ?;
-- 额度应该增加

-- 检查日志
SELECT * FROM ai_quota_log 
WHERE user_id = ? AND change_type = 'purchase'
ORDER BY created_at DESC;
-- 应该有新的日志记录
```

## 注意事项

### ⚠️ 幂等性

由于微信可能重试推送同一订单，必须确保：
- 相同订单多次推送只处理一次
- 已处理的订单状态不为0时直接返回True
- 额度只增加一次

### ⚠️ 事务一致性

支付回调涉及多个表的更新：
- recharge_order 表更新
- user 表更新
- ai_quota_log 表插入

必须确保数据一致性。当前实现使用了 `conn.commit()`。

### ⚠️ 安全性

- 验证签名 ✅
- 验证AppID ✅
- 验证订单存在 ✅
- 验证订单状态 ✅
- 验证金额匹配（可选）
- 验证用户匹配（可选）

### ⚠️ 超时处理

微信推送请求的超时时间为5秒。`handle_midas_payment_callback()` 函数的执行时间应该 < 5秒。

## 常见问题

### Q1: 为什么订单状态没有更新？

**可能原因：**
- 数据库连接失败
- SQL执行错误
- 订单不存在

**解决：**
- 检查数据库配置
- 查看error日志
- 确认订单存在

### Q2: 用户额度没有增加？

**可能原因：**
- user表中没有该用户
- 数据库字段名错误

**解决：**
- 确保用户已创建
- 检查字段名是否为'quota'

### Q3: 收到重复推送怎么办？

**自动处理：**
- 第一次：status=0 → 处理 → status=3
- 第二次：status≠0 → 直接返回True（幂等）

无需额外处理。

## 监控建议

### 关键指标

1. **回调成功率** - 应接近100%
2. **平均处理时间** - 应 < 1秒
3. **订单完成时间** - 应 < 5秒

### 告警设置

- 订单处理失败
- 数据库连接超时
- 额度更新异常

## 参考资源

- [微信安全模式消息处理](./wechat_encrypt.md)
- [微信米大师支付文档](https://developers.weixin.qq.com/minigame/dev/guide/open-ability/midas-payment.html)
- [消息推送事件文档](https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Service_Center_messages.html)
