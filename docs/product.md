# 内容信息获取与修改 API 文档

**更新时间**: 2026年1月20日

## 环境配置

| 环境 | 地址 |
|------|------|
| 测试环境 | `localhost:8000/` |
| 正式环境 | `api.zhongrongxinfu.cn/` |

---

## 产品管理接口

## 1. 获取产品列表

### 接口信息
- **方法**: `GET` 或 `POST`
- **路由**: `/product/list/<f>/`
- **认证**: 否
- **描述**: 获取产品列表，支持多个平台的不同展示方式，新增分页、排序与多条件检索

### 请求参数shang

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| f | string | URL路径 | 是 | 平台类型，可选值: `miniprogram`、`manager-component`、`manager` |
| page | int | Query | 否 | 页码，从1开始，默认1 |
| range | int | Query | 否 | 每页条数，1-500，默认10 |
| sort_by | string | Query | 否 | 排序字段：`updated_at`、`created_at`、`price`、`is_online`、`is_home_visible`、`name`，默认 `updated_at` |
| order | string | Query | 否 | 排序方向：`asc` / `desc`，默认 `desc` |
| name | string | Query | 否 | 按产品名称模糊搜索 |
| tag | string | Query | 否 | 按标签模糊搜索 |
| manager | string | Query | 否 | 按产品经理模糊搜索 |
| department | string | Query | 否 | 按部门模糊搜索 |
| is_online | int | Query | 否 | 是否上线：`0`/`1`（`miniprogram` 和 `manager-component` 固定在线） |
| is_home_visible | int | Query | 否 | 是否在小程序首页产品列表展示：`0`/`1`；`manager` 支持按该字段筛选，`miniprogram` 固定为 `1` |
| price | number | Query | 否 | 价格精确匹配 |
| price_min | number | Query | 否 | 价格下限 |
| price_max | number | Query | 否 | 价格上限 |
| created_start | datetime | Query | 否 | 创建时间起，格式 `YYYY-MM-DD HH:MM:SS` |
| created_end | datetime | Query | 否 | 创建时间止，格式 `YYYY-MM-DD HH:MM:SS` |
| updated_start | datetime | Query | 否 | 更新时间起，格式 `YYYY-MM-DD HH:MM:SS` |
| updated_end | datetime | Query | 否 | 更新时间止，格式 `YYYY-MM-DD HH:MM:SS` |

**平台说明**:
- `miniprogram`: 小程序首页产品列表，仅返回 `is_online=1` 且 `is_home_visible=1` 的产品
- `manager-component`: 管理后台组件展示，返回在线产品的完整信息
- `manager`: 管理后台，返回所有产品（包含离线）

### 请求示例
```bash
# 小程序列表（默认第1页，每页10条，按更新时间倒序）
curl -X GET "http://localhost:8000/product/list/miniprogram/"

# 管理后台列表（第2页，每页20条，按价格升序）
curl -X GET "http://localhost:8000/product/list/manager/?page=2&range=20&sort_by=price&order=asc" \
  -H "Authorization: Bearer <admin_token>"
dy
# 管理后台组件：筛选在线 + 按标签模糊 + 价格区间
curl -X GET "http://localhost:8000/product/list/manager-component/?tag=AI&price_min=100&price_max=999" \
  -H "Authorization: Bearer <admin_token>"

# 管理后台列表：按首页展示状态筛选
curl -X GET "http://localhost:8000/product/list/manager/?is_home_visible=0" \
  -H "Authorization: Bearer <admin_token>"

# 按经理和部门模糊搜索，限定创建时间范围
curl -X GET "http://localhost:8000/product/list/manager/?manager=张&department=产品&created_start=2026-01-01%2000:00:00&created_end=2026-01-31%2023:59:59" \
  -H "Authorization: Bearer <admin_token>"
```

### 返回数据类型

#### 小程序版本（200）
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "name": "产品名称",
      "logo": "http://192.168.196.47:8000/static/logo/550e8400-e29b-41d4-a716-446655440000.jpg",
      "tag": "标签",
      "slogan": "产品标语",
      "price": "9999.99",
      "is_online": 1,
      "is_home_visible": 1,
      "bank_name": "中国银行",
      "reference_rate": "年利率4%-6%",
      "loan_amount": "10-1000万",
      "loan_term": "3年",
      "repayment_method": "等额本息",
      "guarantee_method": "抵押",
      "approval_mode": "线上审批",
      "usage_target": "企业主",
      "organization": "中国银行",
      "service_area": "全国",
      "product_features": "额度高，利率低"
    }
  ],
  "pagination": {
    "page": 1,
    "range": 10,
    "total": 100,
    "total_pages": 10
  }
}
```

#### 管理后台版本（200）
```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "name": "产品名称",
      "logo": "http://192.168.196.47:8000/static/logo/550e8400-e29b-41d4-a716-446655440000.jpg",
      "tag": "标签",
      "slogan": "产品标语",
      "price": "9999.99",
      "is_online": 1,
      "is_home_visible": 1,
      "manager": "张三",
      "department": "产品部",
      "description": "产品描述",
      "bank_name": "中国银行",
      "reference_rate": "年利率4%-6%",
      "loan_amount": "10-1000万",
      "loan_term": "3年",
      "repayment_method": "等额本息",
      "guarantee_method": "抵押",
      "approval_mode": "线上审批",
      "usage_target": "企业主",
      "organization": "中国银行",
      "service_area": "全国",
      "product_features": "额度高，利率低",
      "created_at": "2026-01-01 10:00:00",
      "updated_at": "2026-01-17 15:30:00"
    }
  ],
  "pagination": {
    "page": 1,
    "range": 10,
    "total": 100,
    "total_pages": 10
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 参数错误（平台类型不支持，page<1，range不在1-500，排序字段/方向非法等） |

---

## 2. 创建产品

### 接口信息
- **方法**: `POST`
- **路由**: `/product/new/`
- **认证**: 是（需要管理员权限）
- **描述**: 创建新产品，包含产品基本信息和Logo上传

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| name | string | 是 | 产品名称 |
| tag | string | 是 | 产品标签 |
| slogan | string | 是 | 产品标语 |
| price | string | 是 | 产品价格 |
| is_online | int | 是 | 是否上线（0=否，1=是） |
| is_home_visible | int | 否 | 是否在小程序首页产品列表展示，默认 `1` |
| logo | string | 是 | Logo图片URL |
| manager | string | 否 | 产品经理名称 |
| department | string | 否 | 所属部门 |
| description | string | 否 | 产品描述 |
| bank_name | string | 否 | 银行名称，默认"暂无" |
| reference_rate | string | 否 | 参考利率，默认"暂无" |
| loan_amount | string | 否 | 贷款额度，默认"暂无" |
| loan_term | string | 否 | 贷款期限，默认"暂无" |
| repayment_method | string | 否 | 还款方式，默认"暂无" |
| guarantee_method | string | 否 | 担保方式，默认"暂无" |
| approval_mode | string | 否 | 审批模式，默认"暂无" |
| usage_target | string | 否 | 使用对象，默认"暂无" |
| organization | string | 否 | 所属机构，默认"暂无" |
| service_area | string | 否 | 服务区域，默认"暂无" |
| product_features | string | 否 | 产品特色，默认"暂无" |

### 请求示例
```bash
curl -X POST http://localhost:8000/product/new/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "name=新产品" \
  -d "tag=AI工具" \
  -d "slogan=高效率工作助手" \
  -d "price=9999" \
  -d "is_online=1" \
  -d "is_home_visible=1" \
  -d "manager=张三" \
  -d "department=产品部" \
  -d "description=这是一个产品" \
  -d "bank_name=中国银行" \
  -d "reference_rate=年利率4%-6%" \
  -d "loan_amount=10-1000万" \
  -d "loan_term=3年" \
  -d "repayment_method=等额本息" \
  -d "guarantee_method=抵押" \
  -d "approval_mode=线上审批" \
  -d "usage_target=企业主" \
  -d "organization=中国银行" \
  -d "service_area=全国" \
  -d "product_features=额度高，利率低" \
  -d "logo=https://example.com/logo.jpg"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "data": []
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少必要字段或文件上传失败 |
| 403 | 权限不足，需要管理员权限 |
| 401 | 未登陆 |

---

## 3. 更新产品信息

### 接口信息
- **方法**: `POST`
- **路由**: `/product/update/`
- **认证**: 是（需要管理员权限）
- **描述**: 更新产品的基本信息和Logo

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| uuid | string | 是 | 产品的唯一标识符 |
| name | string | 是 | 产品名称 |
| tag | string | 是 | 产品标签 |
| slogan | string | 是 | 产品标语 |
| price | string | 是 | 产品价格 |
| is_online | int | 是 | 是否上线（0=否，1=是） |
| is_home_visible | int | 否 | 是否在小程序首页产品列表展示，默认 `1` |
| logo | string | 是 | Logo图片URL |
| manager | string | 否 | 产品经理名称 |
| department | string | 否 | 所属部门 |
| description | string | 否 | 产品描述 |
| bank_name | string | 否 | 银行名称 |
| reference_rate | string | 否 | 参考利率 |
| loan_amount | string | 否 | 贷款额度 |
| loan_term | string | 否 | 贷款期限 |
| repayment_method | string | 否 | 还款方式 |
| guarantee_method | string | 否 | 担保方式 |
| approval_mode | string | 否 | 审批模式 |
| usage_target | string | 否 | 使用对象 |
| organization | string | 否 | 所属机构 |
| service_area | string | 否 | 服务区域 |
| product_features | string | 否 | 产品特色 |

### 请求示例
```bash
# 更新产品信息
curl -X POST http://localhost:8000/product/update/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "uuid=550e8400-e29b-41d4-a716-446655440000" \
  -d "name=更新后的产品名" \
  -d "tag=更新标签" \
  -d "slogan=新标语" \
  -d "price=8888" \
  -d "is_online=1" \
  -d "is_home_visible=0" \
  -d "logo=http://192.168.196.47:8000/static/logo/new_logo.jpg" \
  -d "manager=李四" \
  -d "department=市场部" \
  -d "bank_name=工商银行" \
  -d "reference_rate=年利率5%-7%" \
  -d "loan_amount=20-2000万" \
  -d "loan_term=5年" \
  -d "repayment_method=先息后本"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "data": []
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少必要字段或产品不存在 |
| 404 | 产品不存在 |
| 403 | 权限不足 |
| 401 | 未登陆 |

---

## 4. 获取产品详情

### 接口信息
- **方法**: `GET` 或 `POST`
- **路由**: `/product/info/<product_uuid>/`
- **认证**: 否
- **描述**: 获取单个产品的详细信息

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| product_uuid | string | URL路径 | 是 | 产品的唯一标识符 |
| rich_text | string | Query | 否 | 是否返回富文本描述，值为 `true` 时返回，默认 `false` |

### 请求示例
```bash
# 获取基本信息
curl -X GET http://localhost:8000/product/info/550e8400-e29b-41d4-a716-446655440000/

# 获取包含富文本的详细信息
curl -X GET http://localhost:8000/product/info/550e8400-e29b-41d4-a716-446655440000/?rich_text=true
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "name": "产品名称",
    "logo": "http://192.168.196.47:8000/static/logo/550e8400-e29b-41d4-a716-446655440000.jpg",
    "tag": "标签",
    "slogan": "产品标语",
    "price": "9999.99",
    "is_online": 1,
    "is_home_visible": 1,
    "manager": "张三",
    "department": "产品部",
    "description": "产品描述",
    "bank_name": "中国银行",
    "reference_rate": "年利率4%-6%",
    "loan_amount": "10-1000万",
    "loan_term": "3年",
    "repayment_method": "等额本息",
    "guarantee_method": "抵押",
    "approval_mode": "线上审批",
    "usage_target": "企业主",
    "organization": "中国银行",
    "service_area": "全国",
    "product_features": "额度高，利率低",
    "created_at": "2026-01-01 10:00:00",
    "updated_at": "2026-01-17 15:30:00",
    "detail_html": "<div>富文本内容...</div>"
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 404 | 产品不存在 |
| 400 | 查询失败 |

---

## 5. 删除产品

### 接口信息
- **方法**: `DELETE`
- **路由**: `/product/delete/<product_uuid>/`
- **认证**: 是（需要管理员权限）
- **描述**: 删除指定的产品

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| product_uuid | string | URL路径 | 是 | 产品的唯一标识符 |

### 请求示例
```bash
curl -X DELETE http://localhost:8000/product/delete/550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <admin_token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "删除成功"
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 删除失败 |
| 403 | 权限不足 |
| 401 | 未登陆 |

---

## 6. 编辑产品富文本内容

### 接口信息
- **方法**: `POST`
- **路由**: `/product/rich-text/edit/`
- **认证**: 是（需要管理员权限）
- **描述**: 编辑产品的详细富文本描述内容

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| uuid | string | 是 | 产品的唯一标识符 |
| data | string | 是 | 富文本HTML内容 |

### 请求示例
```bash
curl -X POST http://localhost:8000/product/rich-text/edit/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "uuid=550e8400-e29b-41d4-a716-446655440000" \
  -d "data=<h1>产品详细描述</h1><p>这是富文本内容...</p>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "data": []
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少必要字段或编辑失败 |
| 403 | 权限不足 |
| 401 | 未登陆 |

---

## 7. 获取产品富文本内容

### 接口信息
- **方法**: `GET`
- **路由**: `/product/rich-text/get/`
- **认证**: 否
- **描述**: 获取产品的富文本HTML内容

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| uuid | string | Query | 是 | 产品的唯一标识符 |

### 请求示例
```bash
curl -X GET http://localhost:8000/product/rich-text/get/?uuid=550e8400-e29b-41d4-a716-446655440000
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "data": {
    "detail_html": "<h1>产品详细描述</h1><p>这是富文本内容...</p>"
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少必要字段或查询失败 |
| 404 | 产品不存在 |

---

## 动态组件接口

## 8. 获取动态组件内容

### 接口信息
- **方法**: `GET`
- **路由**: `/dynamic_components/get/`
- **认证**: 否
- **描述**: 获取动态组件内容，包括标题和轮播图

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| key | string | Query | 是 | 组件类型，可选值: `title`、`swiper` |

**参数说明**:
- `title`: 页面标题组件
- `swiper`: 轮播图组件

### 请求示例
```bash
# 获取标题组件
curl -X GET http://localhost:8000/dynamic_components/get/?key=title

# 获取轮播图组件
curl -X GET http://localhost:8000/dynamic_components/get/?key=swiper
```

### 返回数据类型    

#### 标题组件（200）
```json
{
  "code": 200,
  "data": {
    "title": "页面标题",
    "subtitle": "副标题"
  }
}
```

#### 轮播图组件（200）
```json
{
  "code": 200,
  "data": {
    "images": [
      {
        "id": 1,
        "url": "http://192.168.196.47:8000/static/swiper/1.jpg",
        "title": "图片1"
      },
      {
        "id": 2,
        "url": "http://192.168.196.47:8000/static/swiper/2.jpg",
        "title": "图片2"
      }
    ],
    "metadata": {
      "lastModified": "2026-01-17T10:30:00Z"
    }
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 错误的key参数 |
| 404 | 组件不存在 |
| 500 | 数据库读取失败 |

---

## 9. 更新动态组件内容

### 接口信息
- **方法**: `POST`
- **路由**: `/dynamic_components/update/`
- **认证**: 是（需要管理员权限）
- **描述**: 更新动态组件内容，支持上传新的图片文件

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| key | string | 是 | 组件类型（`title` 或 `swiper`） |
| data | string | 是 | 组件内容的JSON字符串 |
| image_* | file | 取决于key | 轮播图图片文件（key为swiper时） |

**data 参数格式 (swiper)**:
```json
{
  "images": [
    {
      "id": 1,
      "url": "http://192.168.196.47:8000/static/swiper/1.jpg",
      "title": "图片1"
    },
    {
      "id": 2,
      "url": "http://192.168.196.47:8000/static/swiper/2.jpg",
      "title": "图片2"
    }
  ],
  "metadata": {
    "lastModified": "2026-01-17T10:30:00Z"
  }
}
```

### 请求示例
```bash
# 更新轮播图组件（需要上传图片）
curl -X POST http://localhost:8000/dynamic_components/update/ \
  -H "Authorization: Bearer <admin_token>" \
  -F "key=swiper" \
  -F 'data={"images":[{"id":1,"url":"","title":"图1"},{"id":2,"url":"","title":"图2"}],"metadata":{"lastModified":"2026-01-17T10:30:00Z"}}' \
  -F "image_0=@/path/to/image1.jpg" \
  -F "image_1=@/path/to/image2.jpg"

# 更新标题组件
curl -X POST http://localhost:8000/dynamic_components/update/ \
  -H "Authorization: Bearer <admin_token>" \
  -F "key=title" \
  -F 'data={"title":"新标题","subtitle":"新副标题"}'
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "更新成功"
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 错误的key参数或data格式错误或文件不完整 |
| 403 | 权限不足 |
| 401 | 未登陆 |

---

### 常用数据格式说明

### 产品数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | 数据库内部ID |
| uuid | string | 产品唯一标识符 |
| name | string | 产品名称 |
| logo | string | Logo图片URL |
| tag | string | 产品标签 |
| slogan | string | 产品标语 |
| price | string | 产品价格 |
| is_online | int | 是否上线（0=否，1=是） |
| is_home_visible | int | 是否在小程序首页产品列表展示（0=否，1=是），默认 `1` |
| manager | string | 产品经理名称 |
| department | string | 所属部门 |
| description | string | 产品描述 |
| bank_name | string | 银行名称 |
| reference_rate | string | 参考利率 |
| loan_amount | string | 贷款额度 |
| loan_term | string | 贷款期限 |
| repayment_method | string | 还款方式 |
| guarantee_method | string | 担保方式 |
| approval_mode | string | 审批模式 |
| usage_target | string | 使用对象 |
| organization | string | 所属机构 |
| service_area | string | 服务区域 |
| product_features | string | 产品特色 |
| detail_html | string | 富文本HTML内容 |
| created_at | datetime | 创建时间（格式：YYYY-MM-DD HH:MM:SS） |
| updated_at | datetime | 更新时间（格式：YYYY-MM-DD HH:MM:SS） |

---

## 常见错误处理

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| 400 缺少必要字段 | 请求参数不完整 | 检查所有必须参数是否已提供 |
| 403 权限不足 | 非管理员访问管理接口 | 确认当前用户是否有管理员权限 |
| 404 产品不存在 | UUID不正确或产品已删除 | 检查产品UUID或重新获取列表 |
| 500 数据库错误 | 服务器内部错误 | 稍后重试或联系技术支持 |

---

## 版本历史

| 版本 | 日期 | 更新说明 |
|------|------|--------|
| 1.3 | 2026-03-25 | 为产品表新增 `is_home_visible` 字段，支持管理后台筛选，并将小程序首页列表过滤调整为 `is_online=1` 且 `is_home_visible=1` |
| 1.2 | 2026-01-20 | 修改创建和更新产品接口，logo从文件上传改为URL传递 |
| 1.1 | 2026-01-20 | 为产品表新增13个字段：银行名称、参考利率、贷款额度、贷款期限、还款方式、担保方式、审批模式、使用对象、所属机构、服务区域、产品特色 |
| 1.0 | 2026-01-17 | 初始版本，包含7个产品接口和2个动态组件接口 |
