# AI 接口 API 文档

**更新时间**: 2026年1月24日

## 重要变更说明 (2026-01-24)

### 📌 接口流程优化 - 创建会话与处理内容分离

系统已优化接口设计，使得创建会话和处理内容的过程分离，提高了API的灵活性和易用性：

**新流程**：

**创建聊天会话**：
```
POST /ai/chat/new/ 
→ 获取 conversation_id
→ POST /ai/chat/continue/<conversation_id>/ 
→ 发送消息（支持文件）
```
**描述**: 创建分析会话，仅创建会话并返回会话ID。开始分析与后续追问统一使用 `/ai/analyze/<conversation_id>/continue/`（可在 Body 携带 `file_urls`/`file_names`）
**创建分析会话**：
```
POST /ai/analyze/new/ 
→ 获取 conversation_id
→ POST /ai/analyze/<conversation_id>/continue/ 
→ 继续分析或追问（支持携带文件URL）
```

**关键改进**：
- ✅ 创建会话和发送内容流程清晰
- ✅ 更好的错误处理和步骤控制
- ✅ 支持在创建后再决定是否上传文件
- ✅ 提高了API的可扩展性

### 📌 仅支持公网URL - 文件需传入原名

系统现已升级为**仅支持公网URL**的方式传入文件，用户需要同时传入文件的URL和对应的文件原名：

**新版本使用方式**：
```json
{
  "file_urls": [
    "https://example.com/report.pdf",
    "https://cdn.example.com/image.jpg"
  ],
  "file_names": [
    "销售报告2026.pdf",
    "数据展示图.jpg"
  ]
}
```

**参数说明**：
- `file_urls`: 文件的公网URL列表（必须是 http:// 或 https:// 开头）
- `file_names`: 对应的文件原名列表（必须与 file_urls 一一对应）
- **支持的格式**: 仅 PDF 和图片文件（.pdf, .jpg, .jpeg, .png, .gif, .bmp, .webp）

**关键特性**：
- ✅ 无需下载和本地保存
- ✅ 直接传输URL到AI模型
- ✅ 支持CDN和云存储链接
- ✅ 文件类型严格限制（仅PDF和图片）
- ⚠️ URL必须公开可访问（不支持认证链接）

### 📌 DeepSeek 仅接受纯文本

- DeepSeek 不支持 `image_url` / `file_url` 多模态输入，所有附件会被后端转换为纯文本引用（示例：`[图片] https://...`、`[文件] https://...`）。
- 如需真正的多模态（图片/PDF）理解，请使用 `doubao` 模型。

## 环境配置

| 环境 | 地址 |
|------|------|
| 测试环境 | `localhost:8000/` |
| 正式环境 | `api.zhongrongxinfu.cn/` |

---

## 会话管理接口

## 1. 获取用户所有会话列表

### 接口信息
- **方法**: `GET`
- **路由**: `/ai/conversations/`
- **认证**: 是
- **描述**: 获取当前用户的所有会话ID和基本信息

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| model | string | Query | 否 | 按模型筛选，可选值: `deepseek`、`doubao` |
| limit | int | Query | 否 | 返回数量限制，默认100 |
| offset | int | Query | 否 | 分页偏移量，默认0 |

### 请求示例
```bash
curl -X GET "http://localhost:8000/ai/conversations/?limit=50&offset=0" \
  -H "Authorization: Bearer <token>"

# 按模型筛选
curl -X GET "http://localhost:8000/ai/conversations/?model=deepseek&limit=50" \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "data": [
    {
      "id": "conv-550e8400-e29b-41d4-a716-446655440000",
      "model": "deepseek",
      "title": "我的第一个对话",
      "created_at": "2026-01-17T10:00:00Z",
      "updated_at": "2026-01-17T15:30:00Z",
      "message_count": 5
    },
    {
      "id": "conv-550e8400-e29b-41d4-a716-446655440001",
      "model": "doubao",
      "title": "数据分析讨论",
      "created_at": "2026-01-16T09:15:00Z",
      "updated_at": "2026-01-16T14:20:00Z",
      "message_count": 12
    }
  ],
  "total": 2
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 401 | 未登陆或 token 已过期 |

---

## 2. 获取会话历史记录

### 接口信息
- **方法**: `GET`
- **路由**: `/ai/conversation/<conversation_id>/history/`
- **认证**: 是
- **描述**: 获取指定会话的完整历史对话内容和附件列表

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| conversation_id | string | URL路径 | 是 | 会话的唯一标识符 |

### 请求示例
```bash
curl -X GET http://localhost:8000/ai/conversation/conv-550e8400-e29b-41d4-a716-446655440000/history/ \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "data": {
    "id": "conv-550e8400-e29b-41d4-a716-446655440000",
    "model": "deepseek",
    "title": "我的第一个对话",
    "messages": [
      {
        "role": "user",
        "content": "你好，请帮我分析一下这个文件",
        "files": [
          {
            "type": "file_url",
            "url": "https://cdn.example.com/report.pdf",
            "original_name": "年度报告2025.pdf"
          }
        ]
      },
      {
        "role": "assistant",
        "content": "好的，我已经看到您上传的文件了。这是一个PDF文档，共30页..."
      },
      {
        "role": "user",
        "content": "请继续分析这个表格",
        "files": [
          {
            "type": "image_url",
            "url": "https://cdn.example.com/chart.jpg",
            "original_name": "销售数据图.jpg"
          }
        ]
      },
      {
        "role": "assistant",
        "content": "这个表格显示了每个季度的销售数据..."
      }
    ],
    "files": [
      {
        "type": "file_url",
        "url": "https://cdn.example.com/report.pdf",
        "original_name": "年度报告2025.pdf"
      },
      {
        "type": "image_url",
        "url": "https://cdn.example.com/chart.jpg",
        "original_name": "销售数据图.jpg"
      }
    ],
    "created_at": "2026-01-17T10:00:00Z",
    "updated_at": "2026-01-17T15:30:00Z"
  }
}
```

**字段说明**：
- `messages[].files`: （新增）该条用户消息关联的文件对象数组
  - `type`: `file_url`（PDF/文档类）或 `image_url`（图片）
  - `url`: 文件公网地址（必须 http:// 或 https://）
  - `original_name`: 用户提供的原始文件名
- `files`: 会话级别的所有文件列表（与消息结构一致）

**前端展示建议**：
```javascript
// 遍历消息列表，显示原始文件名
messages.forEach(msg => {
  if (msg.role === 'user' && msg.files && msg.files.length > 0) {
    // 在该条用户消息旁边显示附件列表
    msg.files.forEach(file => {
      console.log(`${file.original_name}`);  // 使用原始文件名展示
    });
  }
});
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 401 | 未登陆 |
| 404 | 会话不存在或无权访问 |

---

## 3. 修改会话标题

### 接口信息
- **方法**: `PUT`
/`
- **认证**: 是
- **描述**: 修改指定会话的标题名称

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| conversation_id | string | URL路径 | 是 | 会话的唯一标识符 |
| title | string | Body | 是 | 新的会话标题（最多255个字符） |

### 请求示例
```bash
curl -X PUT http://localhost:8000/ai/conversation/conv-550e8400-e29b-41d4-a716-446655440000/title/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "项目分析报告讨论"
  }'
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "标题已更新",
  "data": {
    "id": "conv-550e8400-e29b-41d4-a716-446655440000",
    "title": "项目分析报告讨论"
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 标题为空或过长（>255字符） |
| 401 | 未登陆 |
| 404 | 会话不存在或无权访问 |

---

## 4. 删除所有会话

### 接口信息
- **方法**: `DELETE`
- **路由**: `/ai/conversation/deleteall/`
- **认证**: 是
- **描述**: 删除当前用户的所有会话及其关联文件

### 请求参数
无参数

### 请求示例
```bash
curl -X DELETE http://localhost:8000/ai/conversation/deleteall/ \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "所有会话已删除",
  "data": {
    "deleted_conversations": 5,
    "deleted_files": 12
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 401 | 未登陆 |
| 500 | 删除过程中出错 |

---

## AI 聊天接口

## 5. 创建新对话

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/chat/new/`
- **认证**: 是
- **描述**: 创建新的AI对话会话，仅创建会话并返回会话ID。发送初始消息请使用 `/ai/chat/continue/<conversation_id>/` 接口

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| model | string | 否 | AI模型，可选值: `deepseek`、`doubao`，默认 `deepseek` |
| title | string | 否 | 会话标题，默认 "新对话" |

### 请求示例
```bash
# 创建新对话
curl -X POST http://localhost:8000/ai/chat/new/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek",
    "title": "数据分析"
  }'

# 创建对话（使用默认模型和标题）
curl -X POST http://localhost:8000/ai/chat/new/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "data": {
    "conversation_id": "conv-550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-uuid",
    "model": "deepseek",
    "title": "数据分析"
  }
}
```

**说明**：
- `conversation_id`: 新创建的会话ID，用于后续对话操作
- 使用返回的 `conversation_id` 调用 `/ai/chat/continue/<conversation_id>/` 接口发送消息

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 不支持的模型 |
| 401 | 未登陆 |

---

## 6. 继续对话

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/chat/continue/<conversation_id>/`
- **认证**: 是
- **描述**: 继续进行已有的对话，发送新的消息并获取AI回复

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| conversation_id | string | 是 | 会话的唯一标识符 |
| prompt | string | 是 | 用户消息内容 |
| file_urls | string | 否 | 文件的公网URL（可多个） |
| file_names | string | 否 | 对应的文件原名（必须与file_urls一一对应） |

**支持的文件格式**: PDF、图片格式（.pdf, .jpg, .jpeg, .png, .gif, .bmp, .webp）

**模型差异**：
- `deepseek`: 不接受多模态。附件会被转成纯文本行：`[图片] <url>` / `[文件] <url>` 与 `prompt` 合并后发给模型。
- `doubao`: 支持 `image_url` / `file_url` 多模态输入，保持原样传递。

### 请求示例
```bash
# 发送简单消息
curl -X POST http://localhost:8000/ai/chat/continue/conv-550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "请继续分析下一部分内容"
  }'

# 发送消息并附加文件URL（流式响应）
curl -X POST http://localhost:8000/ai/chat/continue/conv-550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "请对这两个文件进行对比分析",
    "file_urls": [
      "https://example.com/file1.pdf",
      "https://example.com/file2.jpg"
    ],
    "file_names": [
      "文件A.pdf",
      "对比图表.jpg"
    ]
  }'

# DeepSeek 下的等价请求（附件会自动转成纯文本描述，不会发送 image_url/file_url 给模型）
curl -X POST http://localhost:8000/ai/chat/continue/conv-550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek",
    "prompt": "请基于这些文件给出摘要",
    "file_urls": [
      "https://example.com/report.pdf",
      "https://example.com/figure.png"
    ],
    "file_names": [
      "年度报告.pdf",
      "图例.png"
    ]
  }'
```

### 返回数据类型

#### 流式 SSE 响应
```
event: start
data: {"conversation_id":"conv-xxx","status":"started"}

event: message
data: {"message":"这是AI的响应内容第一部分..."}

event: message
data: {"message":"这是AI的响应内容第二部分..."}

event: end
data: {"status":"completed"}
```

**响应后数据结构**：
如果本次请求上传了新文件，这些文件会自动关联到当前的用户消息：
```json
{
  "messages": [
    // ...之前的消息
    {
      "role": "user",
      "content": "请对这两个文件进行对比分析",
      "files": [
        {
          "type": "file_url",
          "url": "https://example.com/file1.pdf",
          "original_name": "文件A.pdf"
        },
        {
          "type": "image_url",
          "url": "https://example.com/file2.jpg",
          "original_name": "文件B.jpg"
        }
      ]  // 本次上传的文件
    },
    {
      "role": "assistant",
      "content": "对比分析结果..."
    }
  ]
}
```

**注意事项**：
- 如果某条用户消息没有上传文件，则不会有 `files` 字段
- AI 助手的消息（`role: "assistant"`）永远不会有 `files` 字段
- 每个文件对象包含 `type`、`url`、`original_name` 三个字段（不再返回本地路径）
- DeepSeek 场景下，模型收到的内容为纯文本（附件会被转成 `[文件]/[图片] + URL` 描述），但返回的消息结构仍会包含 `files` 数组便于前端展示

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | prompt不能为空或文件上传失败 |
| 401 | 未登陆 |
| 404 | 会话不存在或无权访问 |

---

## 7. 删除对话

### 接口信息
- **方法**: `DELETE`
- **路由**: `/ai/conversation/delete/<conversation_id>/`
- **认证**: 是
- **描述**: 删除指定的对话记录

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| conversation_id | string | URL路径 | 是 | 会话的唯一标识符 |

### 请求示例
```bash
curl -X DELETE http://localhost:8000/ai/conversation/delete/conv-550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "对话已删除"
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 401 | 未登陆 |
| 404 | 对话不存在或无权访问 |

---

## 文件分析接口

分析接口支持快速分析模式（一步完成），以及会话管理模式（灵活追加文件）：

**快速分析** (`/ai/analyze/new/`)：直接传入文件URL，一步完成分析
**会话管理** (`/ai/analyze/<conversation_id>/continue/`)：通过 `/ai/analyze/new/` 创建会话后，使用 `continue` 追加文件与追问

### 8. 创建分析会话（已移除）

该接口已下线。请使用 `/ai/analyze/new/` 创建分析会话，并通过 `/ai/analyze/<conversation_id>/continue/` 发送首条分析请求或追加文件。

---

### 9. 上传分析文件（已移除）

此接口已废弃并移除。请在调用 `/ai/analyze/<conversation_id>/continue/` 时直接通过 Body 传入 `file_urls` 与 `file_names` 即可完成文件引用，无需单独上传步骤。

变更原因：全部采用公网 URL 引用文件，统一由 `continue` 接口处理。

示例请参考下方“继续分析（追问）”章节。

---

### 10. 创建新分析会话

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/new/`
- **认证**: 是
- **描述**: 创建分析会话，仅创建会话并返回会话ID。上传文件和开始分析请分别使用对应的接口

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| analysis_type | string | 否 | 分析类型：`personal`或`company`，默认 `personal` |
| title | string | 否 | 会话标题，默认 "新分析" |

### 请求示例
```bash
# 创建个人分析会话
curl -X POST http://localhost:8000/ai/analyze/new/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_type": "personal",
    "title": "销售报告分析"
  }'

# 创建企业分析会话
curl -X POST http://localhost:8000/ai/analyze/new/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_type": "company",
    "title": "财务分析"
  }'

# 使用默认参数
curl -X POST http://localhost:8000/ai/analyze/new/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "data": {
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-uuid",
    "model": "doubao",
    "analysis_type": "personal",
    "title": "销售报告分析"
  }
}
```

**说明**：
- `conversation_id`: 新创建的分析会话ID
- `model`: 分析使用的模型，固定为 `doubao`
- `analysis_type`: 分析类型（personal 或 company）
- 使用返回的 `conversation_id` 调用后续接口上传文件和进行分析

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 不支持的分析类型 |
| 401 | 未登陆 |

---

### 11. 继续分析（追问）

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/<conversation_id>/continue/`
- **认证**: 是
- **描述**: 在分析会话中继续追问，支持上传新文件

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| conversation_id | string | 是 | 会话ID（URL路径参数） |
| prompt | string | 是 | 追问内容 |
| file_urls | string | 否 | 文件的公网URL（可选） |
| file_names | string | 否 | 对应的文件原名（可选） |

**支持的文件格式**: PDF、图片格式（.pdf, .jpg, .jpeg, .png, .gif, .bmp, .webp）

**注意事项**：
- 每次调用都会扣除配额
- 可以在追问时传入新文件URL，新文件会关联到当前用户消息

### 请求示例
```bash
# 纯文本追问
curl -X POST http://localhost:8000/ai/analyze/550e8400-xxx/continue/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "请针对第二部分的数据再做深入分析"
  }'

# 追问并附加新文件URL
curl -X POST http://localhost:8000/ai/analyze/550e8400-xxx/continue/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "请将这个新数据与之前的对比分析",
    "file_urls": ["https://example.com/new_data.pdf"],
    "file_names": ["新数据文件.pdf"]
  }'
```

### 返回数据类型

#### 流式 SSE 响应
```
event: start
data: {"conversation_id":"550e8400-xxx","status":"started"}

event: progress
data: {"stage":"first_token","elapsed_ms":1234}

event: message
data: {"message":"根据您的追问，我进行了深入分析..."}

event: end
data: {"status":"completed","quota_cost":1}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | prompt不能为空或URL格式错误 |
| 401 | 未登陆 |
| 402 | 配额不足 |
| 404 | 会话不存在或无权访问 |

---

## 兑换码管理接口

### 12. 创建兑换码（管理员）

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/redeem-code/create/`
- **认证**: 是（需要管理员权限）
- **描述**: 批量创建AI配额兑换码

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| amount | int | 否 | 每张兑换码的配额量，默认1 |
| count | int | 否 | 生成兑换码的数量（1-500），默认1 |
| valid_from | datetime | 否 | 生效时间，格式: `YYYY-MM-DD HH:MM:SS` |
| valid_to | datetime | 否 | 过期时间，格式: `YYYY-MM-DD HH:MM:SS` |
| remark | string | 否 | 备注说明 |

### 请求示例
```bash
# 生成100张配额为100的兑换码
curl -X POST http://localhost:8000/ai/redeem-code/create/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "amount=100&count=100&remark=2026年1月活动"

# 生成有时间限制的兑换码
curl -X POST http://localhost:8000/ai/redeem-code/create/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "amount=500&count=50&valid_from=2026-01-20%2000:00:00&valid_to=2026-02-20%2023:59:59"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "兑换码生成成功",
  "data": [
    "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6",
    "Q7R8S9T0U1V2W3X4Y5Z6A7B8C9D0E1F2",
    "G3H4I5J6K7L8M9N0O1P2Q3R4S5T6U7V8"
  ]
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 参数错误（amount/count格式或数值范围） |
| 403 | 权限不足，需要管理员权限 |
| 401 | 未登陆 |

---

### 13. 兑换配额

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/redeem-code/redeem/`
- **认证**: 是
- **描述**: 用户使用兑换码兑换AI配额

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| code | string | 是 | 兑换码内容 |

### 请求示例
```bash
curl -X POST http://localhost:8000/ai/redeem-code/redeem/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "code=A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "兑换成功",
  "data": {
    "code": "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6",
    "amount": 100,
    "user_uuid": "user-550e8400-e29b-41d4-a716-446655440000",
    "used_at": "2026-01-17 10:30:45"
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少code参数，兑换码不存在，已被使用，未生效或已过期 |
| 401 | 未登陆 |

---

### 14. 查看兑换码列表（管理员）

### 接口信息
- **方法**: `GET`
- **路由**: `/ai/redeem-code/list/`
- **认证**: 是（需要管理员权限）
**描述**: 查看所有已创建的兑换码及其使用情况，支持分页、排序和多条件检索

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| page | int | Query | 否 | 页码，从1开始，默认为1。页数越低内容越新 |
| range | int | Query | 否 | 每页数据条数，范围1-500，默认为10 |
| sort_by | string | Query | 否 | 排序字段：`created_at`、`amount`、`valid_from`、`valid_to`、`is_used`，默认 `created_at` |
| order | string | Query | 否 | 排序方向：`asc` 或 `desc`，默认 `desc` |
| is_effective | string | Query | 否 | 有效状态：`active`（当前时间在有效期内）或`inactive`（未生效或已过期） |
| is_used | int | Query | 否 | 是否已使用：`0` 未使用，`1` 已使用 |
| amount | int | Query | 否 | 精确金额匹配 |
| amount_min | int | Query | 否 | 金额范围下限 |
| amount_max | int | Query | 否 | 金额范围上限 |
| used_by | string | Query | 否 | 使用者 `uuid` 精确匹配 |
| code | string | Query | 否 | 兑换码模糊搜索（包含匹配） |
| created_start | datetime | Query | 否 | 创建时间起，格式 `YYYY-MM-DD HH:MM:SS` |
| created_end | datetime | Query | 否 | 创建时间止，格式 `YYYY-MM-DD HH:MM:SS` |
| valid_from_start | datetime | Query | 否 | 生效时间起，格式 `YYYY-MM-DD HH:MM:SS` |
| valid_from_end | datetime | Query | 否 | 生效时间止，格式 `YYYY-MM-DD HH:MM:SS` |
| valid_to_start | datetime | Query | 否 | 过期时间起，格式 `YYYY-MM-DD HH:MM:SS` |
| valid_to_end | datetime | Query | 否 | 过期时间止，格式 `YYYY-MM-DD HH:MM:SS` |

### 请求示例
```bash
# 查询第1页，每页10条数据
curl -X GET http://localhost:8000/ai/redeem-code/list/ \
  -H "Authorization: Bearer <admin_token>"

# 查询第2页，每页50条数据
curl -X GET http://localhost:8000/ai/redeem-code/list/?page=2&range=50 \
  -H "Authorization: Bearer <admin_token>"

# 按金额倒序排序
curl -X GET "http://localhost:8000/ai/redeem-code/list/?sort_by=amount&order=desc" \
  -H "Authorization: Bearer <admin_token>"

# 仅查看当前有效的兑换码（active），按过期时间正序
curl -X GET "http://localhost:8000/ai/redeem-code/list/?is_effective=active&sort_by=valid_to&order=asc" \
  -H "Authorization: Bearer <admin_token>"

# 检索金额在100-500之间，且创建时间在区间内
curl -X GET "http://localhost:8000/ai/redeem-code/list/?amount_min=100&amount_max=500&created_start=2026-01-01%2000:00:00&created_end=2026-01-31%2023:59:59" \
  -H "Authorization: Bearer <admin_token>"

# 按使用者 uuid 精确检索
curl -X GET "http://localhost:8000/ai/redeem-code/list/?used_by=user-550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <admin_token>"

# 兑换码模糊搜索（包含某段字符）
curl -X GET "http://localhost:8000/ai/redeem-code/list/?code=A1B2C3" \
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
      "code": "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6",
      "amount": 100,
      "is_used": 1,
      "used_by": "user-550e8400-e29b-41d4-a716-446655440000",
      "valid_from": "2026-01-20 00:00:00",
      "valid_to": "2026-02-20 23:59:59",
      "remark": "2026年1月活动",
      "created_at": "2026-01-17 10:00:00"
    },
    {
      "code": "Q7R8S9T0U1V2W3X4Y5Z6A7B8C9D0E1F2",
      "amount": 100,
      "is_used": 0,
      "used_by": null,
      "valid_from": "2026-01-20 00:00:00",
      "valid_to": "2026-02-20 23:59:59",
      "remark": "2026年1月活动",
      "created_at": "2026-01-17 10:00:00"
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
| 400 | 参数错误：`page` < 1、`range` 不在 1-500、`order` 非 asc/desc、`sort_by` 非允许字段 |
| 403 | 权限不足 |
| 401 | 未登陆 |

---

## 17. 删除兑换码（管理员）

### 接口信息
- **方法**: `DELETE`
- **路由**: `/ai/redeem-code/delete/`
- **认证**: 是（需要管理员权限）
- **描述**: 删除指定的兑换码

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| codes[] | string | 是 | 要删除的兑换码数组 |

### 请求示例
```bash
curl -X DELETE http://localhost:8000/ai/redeem-code/delete/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "codes[]=A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6&codes[]=Q7R8S9T0U1V2W3X4Y5Z6A7B8C9D0E1F2"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 200,
  "message": "删除成功",
  "data": {
    "deleted_count": 2
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 缺少codes参数 |
| 403 | 权限不足 |
| 401 | 未登陆 |

---

## 流式响应说明

### SSE (Server-Sent Events) 格式
某些接口返回流式响应，使用标准的 SSE 协议：

```
event: event_name
data: JSON_DATA

event: message
data: {"content":"..."} 

event: end
data: {"status":"completed"}
```

新增进度事件：
```
event: progress
data: {"stage":"first_token","elapsed_ms":1234}
```
含义：从请求开始到收到第一个模型输出 token 的耗时（毫秒），便于前端展示“正在处理中”或记录首字节延迟。

### 客户端处理示例（JavaScript）
```javascript
const eventSource = new EventSource('http://localhost:8000/ai/chat/new/', {
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN'
  }
});

eventSource.addEventListener('start', (event) => {
  const data = JSON.parse(event.data);
  console.log('开始对话:', data);
});

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  console.log('收到消息:', data.message);
  // 更新UI显示
});

eventSource.addEventListener('progress', (event) => {
  const data = JSON.parse(event.data);
  console.log('首字节延迟(ms):', data.elapsed_ms);
  // 可在这里更新“正在处理”提示或埋点上报
});

eventSource.addEventListener('end', (event) => {
  const data = JSON.parse(event.data);
  console.log('对话结束');
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  console.error('发生错误:', event);
  eventSource.close();
});
```

### 前端附件展示完整示例

```javascript
// 获取会话历史并展示（包含附件关联）
async function loadConversationHistory(conversationId) {
  const response = await fetch(`/ai/conversation/${conversationId}/history/`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  
  const result = await response.json();
  if (result.code === 0) {
    const { messages } = result.data;
    
    // 渲染消息列表
    messages.forEach(message => {
      renderMessage(message);
    });
  }
}

// 渲染单条消息（自动处理附件关联）
function renderMessage(message) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `message message-${message.role}`;
  
  // 渲染消息内容
  const contentDiv = document.createElement('div');
  contentDiv.className = 'message-content';
  contentDiv.textContent = message.content;
  messageDiv.appendChild(contentDiv);
  
  // 如果是用户消息且包含附件，显示附件列表
  if (message.role === 'user' && message.files && message.files.length > 0) {
    const attachmentsDiv = document.createElement('div');
    attachmentsDiv.className = 'message-attachments';
    
    message.files.forEach(file => {
      const attachmentItem = document.createElement('div');
      attachmentItem.className = 'attachment-item';
      
      // 支持新的对象格式（推荐）和旧的字符串格式
      let fileName, fileUrl;
      if (typeof file === 'object') {
        // 新格式：{type: "file_url" | "image_url", url: "...", original_name: "..."}
        fileName = file.original_name;
        fileUrl = file.url;
      } else {
        // 旧格式：直接是路径/URL 字符串
        fileName = file.split('/').pop();
        fileUrl = file;
      }
      
      attachmentItem.innerHTML = `
        <span class="attachment-icon">📎</span>
        <span class="attachment-name">${fileName}</span>
      `;
      attachmentItem.dataset.fileUrl = fileUrl;  // 保存URL供下载/预览使用
      attachmentsDiv.appendChild(attachmentItem);
    });
    
    messageDiv.appendChild(attachmentsDiv);
  }
  
  // 添加到聊天容器
  document.getElementById('chat-container').appendChild(messageDiv);
}

// 发送带公网 URL 的消息示例（支持 deepseek/doubao）
async function sendMessageWithUrls(conversationId, prompt, fileUrls = [], fileNames = []) {
  const payload = {
    prompt,
    file_urls: fileUrls,
    file_names: fileNames
  };

  const response = await fetch(`/ai/chat/continue/${conversationId}/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  
  // 处理流式响应...
}
```

**CSS 样式建议**：
```css
.message-attachments {
  margin-top: 8px;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
}

.attachment-item {
  display: flex;
  align-items: center;
  padding: 4px 8px;
  margin: 4px 0;
  background: white;
  border-radius: 4px;
  font-size: 14px;
}

.attachment-icon {
  margin-right: 6px;
}

.attachment-name {
  color: #333;
  font-weight: 500;
}
```

---

## 支持的文件格式

| 格式 | 说明 | 最大大小 |
|------|------|--------|
| PDF | 文档格式 | 50MB |
| JPG/JPEG/PNG/GIF/BMP/WEBP | 图片格式 | 50MB |

---

## 常见错误处理

---

## 版本历史

| 版本 | 日期 | 更新说明 |
|------|------|--------|
| 1.9 | 2026-01-24 | **接口调整**：移除 `/ai/analyze/create/` 接口，统一通过 `/ai/analyze/new/` 创建分析会话并用 `continue` 完成首次与后续分析。|
| 1.8 | 2026-01-24 | **接口调整**：移除 `/ai/analyze/<conversation_id>/start/` 接口，首次分析与后续追问统一使用 `continue`（支持在 Body 传入 `file_urls`/`file_names`）。|
| 1.7 | 2026-01-24 | **接口调整**：移除 `/ai/analyze/<conversation_id>/upload/` 接口，统一在 `continue` 接口中通过 `file_urls`/`file_names` 引用文件（公网 URL）。|
| 1.6 | 2026-01-24 | **接口清理**：移除向后兼容的废弃接口 `/ai/chat/new/old/` 和 `/ai/analyze/new/old/`。所有新接口都采用创建会话与处理内容分离的设计 |
| 1.5 | 2026-01-24 | **接口优化**：简化 `/ai/chat/new/` 和 `/ai/analyze/new/` 接口，仅负责创建会话并返回会话ID。发送消息和上传文件改为独立调用对应接口。提高API使用的灵活性和一致性 |
| 1.4 | 2026-01-24 | **重要变更**：升级为仅支持公网URL方式，移除本地文件上传。所有接口现采用 `file_urls` 和 `file_names` 两个参数，文件不下载和保存。严格限制为仅支持 PDF 和图片文件（.pdf, .jpg, .jpeg, .png, .gif, .bmp, .webp）。新增快速分析接口 `/ai/analyze/new/`（推荐使用），会话管理接口 `/ai/analyze/` 系列仍可用。所有URL必须公开可访问 |
| 1.3 | 2026-01-22 | 拆分分析接口为三步流程，支持灵活的文件管理。新增 `/analyze/create/`、`/analyze/<conversation_id>/upload/`、`/analyze/<conversation_id>/start/` 接口 |
| 1.2 | 2026-01-22 | 优化文件关联机制，文件对象包含 `path` 和 `original_name` 两个字段 |
| 1.1 | 2026-01-22 | 文件关联到具体的用户消息中（`messages[].files`） |
| 1.0 | 2026-01-17 | 初始版本 |
