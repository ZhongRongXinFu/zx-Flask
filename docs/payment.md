# 微信AI额度充值接口文档

## 概述

本系统实现了基于**米大师虚拟支付（现金直付）**的AI额度充值功能。用户直接使用现金购买AI额度，无需购买代币。

## 系统架构

```
用户 -> 小程序前端 -> 小程序服务端 -> 米大师虚拟支付 -> AI额度到账
```

## 主要流程

1. **选择套餐**：用户选择AI额度套餐（如10点额度 9.9元）
2. **创建订单**：系统创建充值订单
3. **发起支付**：调用米大师 jsapi 接口，用户支付现金
4. **支付回调**：米大师通知支付结果
5. **发货完成**：系统增加用户AI额度并通知米大师发货完成

## 配置说明

### 1. 数据库配置

需要执行以下SQL创建表结构：

```sql
-- 套餐表
CREATE TABLE `ai_package` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `package_id` VARCHAR(50) NOT NULL COMMENT '套餐名称',
  `quota_amount` INT NOT NULL COMMENT '额度数量',
  `price` INT NOT NULL COMMENT '价格(分)',
  `description` VARCHAR(255) NULL COMMENT '描述',
  `is_active` TINYINT DEFAULT 1 COMMENT '是否启用',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT 'AI套餐表';

-- 订单表
CREATE TABLE `recharge_order` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `order_no` VARCHAR(64) NOT NULL COMMENT '订单号',
  `user_id` INT NOT NULL COMMENT '用户ID',
  `uuid` VARCHAR(64) NOT NULL COMMENT '用户UUID',
  `plan` VARCHAR(64) NOT NULL COMMENT '套餐ID',
  `quota_amount` INT NOT NULL COMMENT '购买额度数量',
  `price` INT NOT NULL COMMENT '订单金额(分)',
  `wx_order_id` VARCHAR(128) NULL COMMENT '微信订单号',
  `wx_transaction_id` VARCHAR(128) NULL COMMENT '微信支付交易号',
  `status` TINYINT DEFAULT 0 NOT NULL COMMENT '订单状态: 0-待支付, 1-支付中, 2-已支付, 3-已完成, 4-已取消, 5-已退款',
  `pay_time` TIMESTAMP NULL COMMENT '支付时间',
  `complete_time` TIMESTAMP NULL COMMENT '完成时间',
  `user_ip` VARCHAR(50) NULL COMMENT '用户IP',
  `remark` TEXT NULL COMMENT '备注',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY `order_no` (`order_no`),
  KEY `user_id` (`user_id`),
  KEY `uuid` (`uuid`),
  KEY `status` (`status`),
  KEY `wx_transaction_id` (`wx_transaction_id`)
) COMMENT 'AI额度充值订单表';

-- AI额度变动日志表
CREATE TABLE `ai_quota_log` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT NOT NULL COMMENT '用户ID',
  `uuid` VARCHAR(64) NOT NULL COMMENT '用户UUID',
  `change_type` VARCHAR(20) NOT NULL COMMENT '变动类型: redeem-兑换码充值, consume-AI消耗, refund-退款, admin-管理员调整, purchase-购买充值',
  `change_amount` INT NOT NULL COMMENT '变动额度（正数为增加，负数为减少）',
  `quota_before` INT NOT NULL COMMENT '变动前AI额度',
  `quota_after` INT NOT NULL COMMENT '变动后AI额度',
  `related_id` VARCHAR(128) NULL COMMENT '关联ID（兑换码/会话ID/订单号等）',
  `remark` TEXT NULL COMMENT '备注说明',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  KEY `user_id` (`user_id`),
  KEY `uuid` (`uuid`),
  KEY `change_type` (`change_type`),
  KEY `created_at` (`created_at`)
) COMMENT 'AI额度变动日志表';
```

### 2. 微信小程序配置

在 `pages/payment.py` 文件中配置以下参数：

```python
WECHAT_APPID = "your_appid"  # 小程序AppID
WECHAT_APP_SECRET = "your_app_secret"  # 小程序AppSecret  
WECHAT_OFFER_ID = "your_offer_id"  # 米大师分配的offer_id
ENV_TYPE = 0  # 0-正式环境 1-沙箱环境
```

### 3. 米大师虚拟支付配置

需要在微信公众平台完成以下配置：
1. 开通米大师虚拟支付功能
2. 在米大师后台创建道具（AI额度套餐）
3. 获取 offer_id
4. 配置支付回调通知地址
5. 上传道具图片和信息

## API接口说明

### 1. 获取套餐列表

**请求地址**：`GET /payment/packages`

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "name": "入门包",
      "quota": 10,
      "price": 990,
      "price_yuan": 9.9,
      "description": "个人/轻量体验"
    }
  ]
}
```

### 2. 查询用户AI额度

**请求地址**：`GET /payment/quota`

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "current_quota": 76,
    "personal_cost": 1,
    "company_cost": 2
  }
}
```

### 3. 创建充值订单

**请求地址**：`POST /payment/create_order`

**请求参数**：
```json
{
  "uuid": "用户UUID",
  "package_id": 1,
  "openid": "用户openid"
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "order_id": 123,
    "order_no": "RO1706889600000abcdefgh",
    "package_name": "入门包",
    "quota_amount": 10,
    "price": 990,
    "price_yuan": 9.9
  }
}
```

### 4. 发起支付

**请求地址**：`POST /payment/pay`

**请求参数**：
```json
{
  "order_no": "RO1706889600000abcdefgh"
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "prepay_id": "wx20240204100000abcdefgh",
    "order_no": "RO1706889600000abcdefgh"
  }
}
```

**说明**：
- 返回的 `prepay_id` 用于小程序端调用 `wx.requestVirtualPayment()` 发起支付
- 用户完成支付后，米大师会通过回调通知服务器

### 5. 支付回调通知（米大师回调）

**回调消息类型**：`xpay_goods_deliver_notify`

**说明**：
- 此消息由米大师服务器推送到小程序消息服务器
- 服务器收到后需要调用 `notify_provide_goods` 接口确认发货
- 自动给用户增加AI额度并记录日志
- 返回 `{"errcode": 0}` 表示处理成功

### 6. 查询订单详情

**请求地址**：`GET /payment/order/<order_no>`

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "order_no": "RO1706889600000abcdefgh",
    "quota_amount": 10,
    "price": 990,
    "price_yuan": 9.9,
    "status": 3,
    "status_text": "已完成",
    "pay_time": "2024-02-04 10:00:00",
    "complete_time": "2024-02-04 10:00:01",
    "created_at": "2024-02-04 09:59:00",
    "package_name": "入门包",
    "description": "个人/轻量体验"
  }
}
```

### 6. 查询用户订单列表

**请求地址**：`GET /payment/orders?uuid=xxx&page=1&page_size=10`

**响应示例**：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 5,
    "page": 1,
    "page_size": 10,
    "orders": [
      {
        "order_no": "RO1706889600000abcdefgh",
        "quota_amount": 10,
        "price": 990,
        "price_yuan": 9.9,
        "status": 3,
        "status_text": "已完成",
        "pay_time": "2024-02-04 10:00:00",
        "complete_time": "2024-02-04 10:00:01",
        "created_at": "2024-02-04 09:59:00",
        "package_name": "入门包"
      }
    ]
  }
}
```

### 7. 退款接口

**请求地址**：`POST /payment/refund`

**请求参数**：
```json
{
  "order_no": "RO1706889600000abcdefgh",
  "openid": "用户openid",
  "session_key": "用户session_key"
}
```

**响应示例**：
```json
{
  "code": 0,
  "message": "退款成功",
  "data": {
    "refund_order_no": "RF1706889600000abcdefgh",
    "refund_amount": 990
  }
}
```

## 订单状态说明

| 状态码 | 状态名称 | 说明 |
|--------|----------|------|
| 0 | 待支付 | 订单已创建，等待用户支付 |
| 1 | 支付中 | 用户已发起支付，等待微信确认 |
| 2 | 已支付 | 微信支付成功，等待系统处理 |
| 3 | 已完成 | 订单完成，AI额度已到账 |
| 4 | 已取消 | 订单已取消 |
| 5 | 已退款 | 订单已退款，AI额度已扣除 |

## 前端调用示例

### 微信小程序适配指南

#### 1. 环境要求

- 微信小程序基础库版本 >= 2.17.0（支持 `wx.requestVirtualPayment`）
- 小程序需要绑定米大师权限
- 已获得用户的 `openid` 和 `sessionKey`

#### 2. 完整支付流程

```javascript
// 支付工具类
class PaymentService {
  constructor(config) {
    this.baseUrl = config.baseUrl;
    this.token = config.token;
  }

  // 获取当前AI额度
  async getQuota() {
    return wx.request({
      url: `${this.baseUrl}/payment/quota`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${this.token}`
      }
    }).then(res => {
      if (res.statusCode === 200 && res.data.code === 0) {
        return res.data.data.current_quota;
      }
      throw new Error(res.data.message || '获取额度失败');
    });
  }

  // 创建订单
  async createOrder(packageId) {
    return wx.request({
      url: `${this.baseUrl}/payment/create_order`,
      method: 'POST',
      header: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      data: {
        uuid: wx.getStorageSync('uuid'),
        package_id: packageId,
        openid: wx.getStorageSync('openid')
      }
    }).then(res => {
      if (res.statusCode === 200 && res.data.code === 0) {
        return res.data.data;
      }
      throw new Error(res.data.message || '创建订单失败');
    });
  }

  // 发起支付
  async startPayment(orderNo) {
    // 1. 调用后端获取prepay_id
    const payResult = await wx.request({
      url: `${this.baseUrl}/payment/pay`,
      method: 'POST',
      header: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      data: {
        order_no: orderNo
      }
    }).then(res => {
      if (res.statusCode === 200 && res.data.code === 0) {
        return res.data.data;
      }
      throw new Error(res.data.message || '获取支付参数失败');
    });

    // 2. 调起虚拟支付
    return new Promise((resolve, reject) => {
      wx.requestVirtualPayment({
        prepayId: payResult.prepay_id,
        success(res) {
          // 用户确认支付，返回结果
          resolve({
            code: 0,
            message: '支付成功',
            data: payResult
          });
        },
        fail(err) {
          // 支付失败或用户取消
          if (err.errCode === -1) {
            reject({
              code: -1,
              message: '用户取消支付'
            });
          } else {
            reject({
              code: -2,
              message: `支付失败: ${err.errMsg}`
            });
          }
        }
      });
    });
  }

  // 查询订单状态
  async getOrderDetail(orderNo) {
    return wx.request({
      url: `${this.baseUrl}/payment/order/${orderNo}`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${this.token}`
      }
    }).then(res => {
      if (res.statusCode === 200 && res.data.code === 0) {
        return res.data.data;
      }
      throw new Error(res.data.message || '查询订单失败');
    });
  }

  // 获取用户订单列表
  async getUserOrders(page = 1, pageSize = 10) {
    return wx.request({
      url: `${this.baseUrl}/payment/orders?page=${page}&page_size=${pageSize}`,
      method: 'GET',
      header: {
        'Authorization': `Bearer ${this.token}`
      }
    }).then(res => {
      if (res.statusCode === 200 && res.data.code === 0) {
        return res.data.data;
      }
      throw new Error(res.data.message || '获取订单列表失败');
    });
  }

  // 申请退款
  async refundOrder(orderNo) {
    return wx.request({
      url: `${this.baseUrl}/payment/refund`,
      method: 'POST',
      header: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      data: {
        order_no: orderNo
      }
    }).then(res => {
      if (res.statusCode === 200 && res.data.code === 0) {
        return res.data.data;
      }
      throw new Error(res.data.message || '申请退款失败');
    });
  }
}

// 使用示例
const paymentService = new PaymentService({
  baseUrl: 'https://your-domain.com',
  token: wx.getStorageSync('token')
});
```

#### 3. 在页面中的使用

```javascript
// pages/ai-recharge/ai-recharge.js
Page({
  data: {
    packages: [],
    currentQuota: 0,
    selectedPackageId: null,
    loading: false,
    orders: [],
    paymentService: null
  },

  async onLoad() {
    this.setData({
      paymentService: new PaymentService({
        baseUrl: 'https://your-domain.com',
        token: wx.getStorageSync('token')
      })
    });
    
    // 初始化页面
    await this.loadPackages();
    await this.loadCurrentQuota();
    await this.loadOrders();
  },

  // 加载套餐列表
  async loadPackages() {
    try {
      const res = await wx.request({
        url: 'https://your-domain.com/payment/packages',
        method: 'GET'
      });
      
      if (res.statusCode === 200 && res.data.code === 0) {
        this.setData({
          packages: res.data.data
        });
      }
    } catch (error) {
      wx.showToast({
        title: '加载套餐失败',
        icon: 'none'
      });
    }
  },

  // 加载当前额度
  async loadCurrentQuota() {
    try {
      const quota = await this.data.paymentService.getQuota();
      this.setData({
        currentQuota: quota
      });
    } catch (error) {
      wx.showToast({
        title: error.message || '获取额度失败',
        icon: 'none'
      });
    }
  },

  // 加载订单列表
  async loadOrders() {
    try {
      const data = await this.data.paymentService.getUserOrders(1, 5);
      this.setData({
        orders: data.orders || []
      });
    } catch (error) {
      console.error('获取订单列表失败:', error);
    }
  },

  // 选择套餐
  selectPackage(e) {
    const packageId = e.currentTarget.dataset.id;
    this.setData({
      selectedPackageId: packageId
    });
  },

  // 立即充值
  async onPay() {
    if (!this.data.selectedPackageId) {
      wx.showToast({
        title: '请选择套餐',
        icon: 'none'
      });
      return;
    }

    this.setData({ loading: true });

    try {
      // 1. 创建订单
      wx.showLoading({ title: '创建订单中...' });
      const orderData = await this.data.paymentService.createOrder(
        this.data.selectedPackageId
      );
      wx.hideLoading();

      // 2. 发起支付
      wx.showLoading({ title: '发起支付中...' });
      const paymentResult = await this.data.paymentService.startPayment(
        orderData.order_no
      );
      wx.hideLoading();

      // 3. 支付成功
      wx.showToast({
        title: '支付成功',
        icon: 'success'
      });

      // 刷新额度和订单列表
      await this.loadCurrentQuota();
      await this.loadOrders();

      // 返回到前一页或首页
      setTimeout(() => {
        wx.navigateBack({
          delta: 1,
          fail: () => {
            wx.reLaunch({ url: '/pages/index/index' });
          }
        });
      }, 1500);

    } catch (error) {
      wx.hideLoading();
      
      // 处理不同的错误情况
      if (error.code === -1) {
        wx.showToast({
          title: error.message || '支付失败',
          icon: 'none'
        });
      } else {
        wx.showModal({
          title: '支付失败',
          content: error.message || '未知错误，请重试',
          confirmText: '重试',
          success: (res) => {
            if (res.confirm) {
              this.onPay(); // 重试
            }
          }
        });
      }
    } finally {
      this.setData({ loading: false });
    }
  },

  // 申请退款
  async refundOrder(e) {
    const orderNo = e.currentTarget.dataset.orderNo;
    
    wx.showModal({
      title: '确认退款',
      content: '确认要退款此订单吗？AI额度将被扣除。',
      confirmText: '确认退款',
      success: async (res) => {
        if (res.confirm) {
          try {
            wx.showLoading({ title: '处理中...' });
            await this.data.paymentService.refundOrder(orderNo);
            wx.hideLoading();
            
            wx.showToast({
              title: '退款成功',
              icon: 'success'
            });
            
            // 刷新数据
            await this.loadCurrentQuota();
            await this.loadOrders();
          } catch (error) {
            wx.hideLoading();
            wx.showToast({
              title: error.message || '退款失败',
              icon: 'none'
            });
          }
        }
      }
    });
  }
});
```

#### 4. 错误处理和状态检查

```javascript
// 重要：支付后的状态检查
async function checkPaymentStatus(orderNo, maxRetries = 10) {
  let retries = 0;
  const checkInterval = setInterval(async () => {
    try {
      const orderDetail = await paymentService.getOrderDetail(orderNo);
      
      if (orderDetail.status === 3) {
        // 订单已完成，支付成功
        clearInterval(checkInterval);
        wx.showToast({
          title: '充值成功',
          icon: 'success'
        });
        return;
      } else if (orderDetail.status === 4 || orderDetail.status === 5) {
        // 订单已取消或退款
        clearInterval(checkInterval);
        wx.showToast({
          title: '订单异常',
          icon: 'none'
        });
        return;
      }
      
      retries++;
      if (retries >= maxRetries) {
        clearInterval(checkInterval);
        wx.showToast({
          title: '支付超时，请稍后查询订单状态',
          icon: 'none'
        });
      }
    } catch (error) {
      clearInterval(checkInterval);
      console.error('查询订单状态失败:', error);
    }
  }, 1000); // 每秒检查一次
}

// 处理支付异常情况
function handlePaymentError(errorCode) {
  const errorMap = {
    '-1': '用户取消了支付',
    '-2': '支付失败，请检查网络',
    '-3': '支付超时，请稍后重试',
    '-4': '支付参数错误',
    '-5': '用户账户异常'
  };
  
  return errorMap[errorCode] || '支付出错，请重试';
}
```

#### 5. 网络请求优化

```javascript
// 添加超时和重试机制
class PaymentServiceWithRetry {
  constructor(config) {
    this.baseUrl = config.baseUrl;
    this.token = config.token;
    this.timeout = config.timeout || 10000;
    this.maxRetries = config.maxRetries || 3;
  }

  async request(url, options = {}) {
    let lastError;
    
    for (let i = 0; i < this.maxRetries; i++) {
      try {
        return await Promise.race([
          wx.request({
            url,
            timeout: this.timeout,
            header: {
              'Authorization': `Bearer ${this.token}`,
              'Content-Type': 'application/json',
              ...options.header
            },
            ...options
          }),
          new Promise((_, reject) => 
            setTimeout(() => reject(new Error('请求超时')), this.timeout)
          )
        ]);
      } catch (error) {
        lastError = error;
        console.log(`请求失败，第 ${i + 1} 次重试...`);
        
        if (i < this.maxRetries - 1) {
          // 指数退避重试
          await new Promise(resolve => 
            setTimeout(resolve, Math.pow(2, i) * 1000)
          );
        }
      }
    }
    
    throw lastError;
  }

  async startPaymentWithRetry(orderNo) {
    return this.request(`${this.baseUrl}/payment/pay`, {
      method: 'POST',
      data: { order_no: orderNo }
    }).then(res => {
      if (res.statusCode === 200 && res.data.code === 0) {
        return res.data.data;
      }
      throw new Error(res.data.message || '获取支付参数失败');
    });
  }
}
```

### 小程序端调用流程

```javascript
// 1. 查询用户当前AI额度
wx.request({
  url: 'https://your-domain.com/payment/quota',
  method: 'GET',
  header: {
    'Authorization': 'Bearer ' + token
  },
  success(res) {
    console.log('当前AI额度:', res.data.data.current_quota);
  }
});

// 2. 创建订单
wx.request({
  url: 'https://your-domain.com/payment/create_order',
  method: 'POST',
  header: {
    'Authorization': 'Bearer ' + token
  },
  data: {
    uuid: 'user_uuid',
    package_id: 1,
    openid: 'user_openid'
  },
  success(res) {
    const orderNo = res.data.data.order_no;
    
    // 3. 发起支付
    wx.request({
      url: 'https://your-domain.com/payment/pay',
      method: 'POST',
      header: {
        'Authorization': 'Bearer ' + token
      },
      data: {
        order_no: orderNo
      },
      success(payRes) {
        if (payRes.data.code === 0) {
          // 调起米大师虚拟支付
          wx.requestVirtualPayment({
            prepayId: payRes.data.data.prepay_id,
            success(paymentRes) {
              wx.showToast({
                title: '支付成功',
                icon: 'success'
              });
              // 支付成功后查询订单状态或刷新余额
            },
            fail(err) {
              wx.showToast({
                title: '支付失败',
                icon: 'none'
              });
            }
          });
        }
      }
    });
  }
});
```

## 注意事项

1. **米大师虚拟支付说明**
   - 使用米大师 jsapi 接口进行现金支付
   - 用户直接支付现金购买AI额度
   - 无需购买和使用代币，简化流程

2. **道具配置**
   - 需要在米大师后台配置AI额度套餐作为道具
   - 道具价格必须与系统套餐价格一致
   - 上传道具图片和描述信息

3. **安全性**
   - 所有接口都需要验证签名（pay_sig）
   - 回调消息必须验证来源和签名
   - 建议使用HTTPS加密传输
   - 在后端缓存 access_token

4. **支付回调处理**
   - 米大师支付成功后会推送 `xpay_goods_deliver_notify` 消息
   - 收到消息后必须调用 `notify_provide_goods` 确认发货
   - 回调可能重复发送，需要做幂等性处理
   - 未确认发货的订单可能被自动退款

5. **订单幂等性**
   - 同一订单号只能支付一次
   - 支付前会检查订单状态
   - 发货确认需要做幂等性处理

6. **退款限制**
   - 只有已完成的订单才能退款
   - 退款会扣减用户的AI额度
   - 用户AI额度不足时无法退款
   - 使用 `refund_order` 接口进行退款

7. **环境配置**
   - 开发测试时使用沙箱环境（ENV_TYPE=1）
   - 生产环境使用正式环境（ENV_TYPE=0）

8. **日志系统**
   - `ai_quota_log` 记录所有AI额度变动
   - 包括：购买充值、兑换码充值、AI消耗、退款等

## AI额度变动日志查询接口

### 8. 查询用户AI额度变动日志

**请求地址**：`GET /ai/quota/logs/?change_type=consume&page=1&page_size=50`

**请求参数**：
- `change_type`（可选）：变动类型（redeem/consume/purchase/refund/admin）
- `page`：页码，默认1
- `page_size`：每页数量，默认50，最大200

**响应示例**：
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "user_id": 123,
      "uuid": "user-uuid-xxx",
      "change_type": "consume",
      "change_type_text": "AI对话消耗",
      "change_amount": -1,
      "quota_before": 76,
      "quota_after": 75,
      "related_id": "conversation-id-xxx",
      "remark": "AI对话消耗(personal类型)",
      "created_at": "2026-02-04 10:30:00"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 100,
    "total_pages": 2
  }
}
```

### 9. 查询所有用户AI额度变动日志（管理员）

**请求地址**：`GET /ai/quota/logs/all/?uuid=xxx&change_type=redeem&page=1&page_size=50`

**请求参数**：
- `uuid`（可选）：用户UUID，用于筛选特定用户
- `change_type`（可选）：变动类型
- `page`：页码，默认1
- `page_size`：每页数量，默认50，最大200

**权限要求**：管理员

**响应格式**：与用户查询接口相同

## AI额度变动类型说明

| 类型 | 英文标识 | 说明 | 触发场景 |
|------|----------|------|----------|
| 兑换码充值 | redeem | 用户使用兑换码增加额度 | 用户输入兑换码并验证成功 |
| AI对话消耗 | consume | AI分析对话消耗额度 | 用户进行AI分析（personal消耗1，company消耗2） |
| 购买充值 | purchase | 用户购买套餐增加额度 | 用户使用代币购买AI额度套餐 |
| 退款 | refund | 订单退款扣减额度 | 用户申请退款，系统扣减相应额度 |
| 管理员调整 | admin | 管理员手动调整额度 | 管理员后台操作（预留功能） |

## 错误码参考

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| -1 | 系统错误 |
| 400 | 请求参数错误 |
| 401 | 未登录或token过期 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 相关文档

- [米大师虚拟支付文档](https://developers.weixin.qq.com/minigame/dev/guide/open-ability/midas-payment.html)
- [米大师 jsapi 接口](https://developers.weixin.qq.com/minigame/dev/api-backend/midas-payment/midas-payment.presentCurrency.html)
- [小程序虚拟支付](https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/midas-payment.html)
