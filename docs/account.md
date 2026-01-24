# 账号登陆功能 API 文档

**更新时间**: 2026年1月17日

## 环境配置

| 环境 | 地址 |
|------|------|
| 测试环境 | `localhost:8000/` |
| 正式环境 | `api.zhongrongxinfu.cn/` |

---

## 1. 微信OAuth登陆回调处理

### 接口信息
- **方法**: `GET`
- **路由**: `/account/oauth/wechat/callback/`
- **认证**: 否
- **描述**: 处理微信OAuth回调，验证用户身份并生成登陆token

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| code | string | 是 | 微信授权服务器返回的授权码 |
| state | string | 是 | 应用定义的状态参数，格式为 `<state_id>;<redirect_uri>` |

**state 参数说明**:
- `state_id`: 自定义状态标识（数字）
- `redirect_uri`: 登陆后的重定向地址，使用`;`分隔

**示例 URL**:
```
http://localhost:8000/account/oauth/wechat/callback/?code=ABC123XYZ&state=0;http://localhost:5173/redirect
```

### 返回数据类型

#### 成功（302 重定向）
```json
{
  "redirect_uri": "http://localhost:5173/redirect?token=<JWT_TOKEN>"
}
```

#### 错误响应
```json
{
  "code": 400,
  "message": "缺少 code 或登陆失败原因描述",
  "error": "error_details"
}
```

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少 code 参数或获取 access_token 失败 |
| 403 | 用户不是管理员（需要 is_op=1） |

### 业务流程
1. 验证微信授权码获取 `access_token` 和 `openid`
2. 使用 `access_token` 获取用户信息
3. 检查用户是否存在，且是否为管理员
4. 生成30天有效期的 JWT token
5. 存储 token 到数据库 `user_token` 表
6. 重定向到指定 URI，并在 URL 参数中携带 token

---

## 2. 管理员登陆

### 接口信息
- **方法**: `POST`
- **路由**: `/account/login/manager/`
- **认证**: 否
- **描述**: 用于管理员快速登陆，基于微信openid

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| openid | string | 是 | 微信用户 openid |

### 请求示例
```bash
curl -X POST http://localhost:8000/account/login/manager/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "openid=oU-J716qXHV4IZwjKhIgymHIYcYg"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "登录token创建成功",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少 openid 参数或账户不存在 |
| 403 | 用户不是管理员（需要 is_op=1） |

### 业务流程
1. 验证 openid 参数
2. 查询用户是否存在于数据库
3. 验证用户是否有管理员权限（is_op=1）
4. 生成30天有效期的 JWT token
5. 存储 token 到数据库

---

## 3. 获取用户资料

### 接口信息
- **方法**: `GET` 或 `POST`
- **路由**: `/account/profile/`
- **认证**: 是（需要有效的 token）
- **描述**: 获取当前登陆用户的个人资料信息

### 请求参数
无参数

### 请求示例
```bash
curl -X GET http://localhost:8000/account/profile/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "获取用户信息成功",
  "data": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "nickname": "张三",
    "wechat": "oU-J716qXHV4IZwjKhIgymHIYcYg",
    "email": "user@example.com",
    "phone": "13812345678",
    "avatar": "http://192.168.196.47:8000/static/avatar/user_avatar.jpg",
    "is_op": 1,
    "vip_type": "silver",
    "vip_expire": "2026-12-31 23:59:59",
    "ai_quota": 5000
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 401 | 未登陆或 token 已过期 |

### 数据字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| uuid | string | 用户唯一标识符 |
| nickname | string | 用户昵称 |
| wechat | string | 微信openid |
| email | string/null | 邮箱地址 |
| phone | string/null | 手机号码 |
| avatar | string/null | 头像URL |
| is_op | int | 是否管理员（0=否，1=是） |
| vip_type | string | VIP类型（copper/silver/gold） |
| vip_expire | datetime/null | VIP过期时间 |
| ai_quota | int | AI服务剩余配额（积分） |

---

## 4. 获取指定用户资料

### 接口信息
- **方法**: `GET`
- **路由**: `/account/info/<uid>/`
- **认证**: 是
- **描述**: 获取指定用户ID的资料信息

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| uid | string | URL路径 | 是 | 用户的 uuid |

### 请求示例
```bash
curl -X GET http://localhost:8000/account/info/550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "data": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "nickname": "张三",
    "wechat": "oU-J716qXHV4IZwjKhIgymHIYcYg",
    "email": "user@example.com",
    "phone": "13812345678",
    "avatar": "http://192.168.196.47:8000/static/avatar/user_avatar.jpg",
    "vip_type": "silver",
    "vip_expire": "2026-12-31 23:59:59",
    "ai_quota": 5000,
    "is_op": 0
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 404 | 用户不存在 |
| 401 | 未登陆或 token 已过期 |

---

## 5. 用户登出

### 接口信息
- **方法**: `DELETE`
- **路由**: `/account/logout/`
- **认证**: 是
- **描述**: 注销当前用户的登陆状态，删除token

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| token | string | Header | 是 | 在 `Authorization: Bearer <token>` 或 `X-Token` 头中 |

### 请求示例
```bash
curl -X DELETE http://localhost:8000/account/logout/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "已退出登录"
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少 token 参数 |
| 401 | 未登陆 |

---

## 6. 获取所有用户列表（管理员）

### 接口信息
- **方法**: `GET`
- **路由**: `/account/getall/`
- **认证**: 是（需要管理员权限）
**描述**: 获取所有用户的列表信息，支持分页、排序和多条件检索，仅管理员可用

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| page | int | Query | 否 | 页码，从1开始，默认1 |
| range | int | Query | 否 | 每页条数，1-500，默认10 |
| sort_by | string | Query | 否 | 排序字段：`created_at`、`ai_quota`、`vip_expire`、`is_op`、`nickname`，默认 `created_at` |
| order | string | Query | 否 | 排序方向：`asc` / `desc`，默认 `desc` |
| nickname | string | Query | 否 | 按昵称模糊搜索 |
| email | string | Query | 否 | 按邮箱模糊搜索 |
| phone | string | Query | 否 | 按手机号模糊搜索 |
| vip_type | string | Query | 否 | VIP 类型精确匹配（如 copper/silver/gold） |

### 请求示例
```bash
# 基础列表（第1页，每页10条，按创建时间降序）
curl -X GET http://localhost:8000/account/getall/ \
  -H "Authorization: Bearer <admin_token>"

# 按 AI 配额倒序，取第2页，每页20条
curl -X GET "http://localhost:8000/account/getall/?page=2&range=20&sort_by=ai_quota&order=desc" \
  -H "Authorization: Bearer <admin_token>"

# 按昵称模糊搜索
curl -X GET "http://localhost:8000/account/getall/?nickname=张" \
  -H "Authorization: Bearer <admin_token>"

# 按邮箱或手机号模糊搜索
curl -X GET "http://localhost:8000/account/getall/?email=@example.com&phone=138" \
  -H "Authorization: Bearer <admin_token>"

# 按 VIP 类型筛选（如 gold）
curl -X GET "http://localhost:8000/account/getall/?vip_type=gold" \
  -H "Authorization: Bearer <admin_token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "查询成功",
  "data": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "nickname": "用户1",
      "wechat": "openid_1",
      "email": "user1@example.com",
      "phone": "13812345678",
      "avatar": "http://example.com/avatar.jpg",
      "vip_type": "silver",
      "vip_expire": "2026-12-31 23:59:59",
      "ai_quota": 5000,
      "is_op": 1,
      "created_at": "2026-01-15 10:00:00"
    },
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440001",
      "nickname": "用户2",
      "wechat": "openid_2",
      "email": "user2@example.com",
      "phone": null,
      "avatar": null,
      "vip_type": "copper",
      "vip_expire": null,
      "ai_quota": 0,
      "is_op": 0,
      "created_at": "2026-01-10 08:30:00"
    }
  ],
  "pagination": {
    "page": 1,
    "range": 10,
    "total": 2,
    "total_pages": 1
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 参数错误（page<1、range 不在1-500、排序字段/方向非法等） |
| 403 | 权限不足，需要管理员权限 |
| 401 | 未登陆或 token 已过期 |

---

## Token 说明

### Token 格式
- **类型**: JWT (JSON Web Token)
- **有效期**: 30天
- **传递方式**: 
  - Header 方式: `Authorization: Bearer <token>`
  - 或: `X-Token: <token>`

### Token 验证
- 每次请求时自动验证 token 有效性
- 过期的 token 会被自动删除
- 无效 token 返回 401 未授权错误

---

## 常见错误处理

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| 401 未登陆 | 未提供token或token无效 | 重新调用登陆接口获取有效token |
| 403 权限不足 | 非管理员访问管理员接口 | 检查账户权限或切换管理员账户 |
| 400 缺少参数 | 请求参数不完整 | 检查请求参数是否齐全 |
| 404 用户不存在 | 指定用户不存在 | 检查用户ID是否正确 |

---

## 调试工具建议

推荐使用 Postman 或 VS Code REST Client 进行 API 测试：

```bash
# VS Code REST Client 示例
### 获取用户资料
GET http://localhost:8000/account/profile/
Authorization: Bearer YOUR_TOKEN_HERE

### 登出
DELETE http://localhost:8000/account/logout/
Authorization: Bearer YOUR_TOKEN_HERE

### 管理员登陆
POST http://localhost:8000/account/login/manager/
Content-Type: application/x-www-form-urlencoded

openid=YOUR_WECHAT_OPENID
```

---

## 版本历史

| 版本 | 日期 | 更新说明 |
|------|------|--------|
| 1.0 | 2026-01-17 | 初始版本，包含6个账户相关接口 |
