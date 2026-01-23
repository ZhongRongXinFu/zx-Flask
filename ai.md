# AI 接口 API 文档

**更新时间**: 2026年1月22日

## 重要变更说明 (2026-01-22)

### 📌 附件关联优化 - 支持原始文件名记录

为了让前端能够准确展示哪些文件属于哪条消息，以及显示原始文件名，我们对消息数据结构进行了优化：

**旧版本**（不推荐）：
```json
{
  "messages": [
    {"role": "user", "content": "请分析这个文件"},
    {"role": "assistant", "content": "好的..."}
  ],
  "files": ["file1.pdf", "file2.png"]  // 仅路径，不知道属于哪条消息，也没有原始文件名
}
```

**新版本**（推荐）：
```json
{
  "messages": [
    {
      "role": "user", 
      "content": "请分析这个文件",
      "files": [
        {
          "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/abc123.pdf",
          "original_name": "销售报告2026.pdf"  // ← 新增：原始文件名
        },
        {
          "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/def456.png",
          "original_name": "data-chart.png"  // ← 新增：原始文件名
        }
      ]  // 关联到这条用户消息
    },
    {"role": "assistant", "content": "好的，我看到您上传了..."}
  ],
  "files": [
    {
      "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/abc123.pdf",
      "original_name": "销售报告2026.pdf"
    },
    {
      "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/def456.png",
      "original_name": "data-chart.png"
    }
  ]  // 保留用于向后兼容
}
```

**前端适配建议**：
1. **优先读取消息内的 `files` 字段**：遍历 `messages` 数组，如果消息有 `files` 字段，则显示在该消息旁边
2. **显示原始文件名**：使用 `files[].original_name` 作为UI展示，这是用户上传时的原始文件名
3. **使用路径加载文件**：实际加载或下载时使用 `files[].path`
4. **兼容旧数据**：如果某条消息没有 `files` 字段，可以回退到使用会话级别的 `files` 数组

**数据结构说明**：
- `messages[].files[].path`: 文件的完整存储路径（后端使用）
- `messages[].files[].original_name`: 用户上传时的原始文件名（前端展示）

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
            "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/abc123.pdf",
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
            "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/def456.xlsx",
            "original_name": "销售数据2025.xlsx"
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
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/abc123.pdf",
        "original_name": "年度报告2025.pdf"
      },
      {
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/def456.xlsx",
        "original_name": "销售数据2025.xlsx"
      }
    ],
    "created_at": "2026-01-17T10:00:00Z",
    "updated_at": "2026-01-17T15:30:00Z"
  }
}
```

**字段说明**：
- `messages[].files`: （新增）该条用户消息关联的文件对象数组
  - `path`: 文件的完整存储路径
  - `original_name`: 用户上传时的原始文件名
- `files`: 会话级别的所有文件列表（向后兼容）

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
- **描述**: 创建新的AI对话，可选择模型并发送初始消息

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| model | string | 否 | AI模型，可选值: `deepseek`、`doubao`，默认 `deepseek` |
| title | string | 否 | 会话标题，默认 "新对话" |
| prompt | string | 否 | 初始消息内容 |
| files | file | 否 | 附加文件（可多个） |

### 请求示例
```bash
# 创建空对话
curl -X POST http://localhost:8000/ai/chat/new/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "model=deepseek&title=数据分析"

# 创建对话并发送初始消息（流式响应）
curl -X POST http://localhost:8000/ai/chat/new/ \
  -H "Authorization: Bearer <token>" \
  -F "model=deepseek" \
  -F "title=PDF分析" \
  -F "prompt=请帮我分析这个PDF文件" \
  -F "files=@/path/to/file.pdf"
```

### 返回数据类型

#### 创建空对话成功（200）
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

#### 发送初始消息（流式 SSE 响应）
```
event: start
data: {"conversation_id":"conv-xxx","status":"started"}

event: message
data: {"message":"这是第一部分响应..."}

event: message
data: {"message":"这是第二部分响应..."}

event: end
data: {"status":"completed"}
```

**响应后数据结构**：
发送初始消息后，会话的消息数据结构会自动包含文件关联信息：
```json
{
  "messages": [
    {
      "role": "user",
      "content": "请帮我分析这个PDF文件",
      "files": [
        {
          "path": "/path/to/file.pdf",
          "original_name": "报告2025.pdf"
        }
      ]
    },
    {
      "role": "assistant",
      "content": "这是AI的完整响应..."
    }
  ],
  "files": [
    {
      "path": "/path/to/file.pdf",
      "original_name": "报告2025.pdf"
    }
  ]
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 不支持的模型或文件上传失败 |
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
| files | file | 否 | 新增附加文件（可多个） |

### 请求示例
```bash
# 发送简单消息
curl -X POST http://localhost:8000/ai/chat/continue/conv-550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "prompt=请继续分析下一部分内容"

# 发送消息并上传新文件（流式响应）
curl -X POST http://localhost:8000/ai/chat/continue/conv-550e8400-e29b-41d4-a716-446655440000/ \
  -H "Authorization: Bearer <token>" \
  -F "prompt=请对这两个文件进行对比分析" \
  -F "files=@/path/to/file1.pdf" \
  -F "files=@/path/to/file2.pdf"
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
          "path": "/path/to/file1.pdf",
          "original_name": "文件A.pdf"
        },
        {
          "path": "/path/to/file2.pdf",
          "original_name": "文件B.pdf"
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
- 每个文件对象包含 `path`（存储路径）和 `original_name`（原始文件名）两个字段

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
- **路由**: `/ai/chat/delete/<conversation_id>/`
- **认证**: 是
- **描述**: 删除指定的对话记录

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| conversation_id | string | URL路径 | 是 | 会话的唯一标识符 |

### 请求示例
```bash
curl -X DELETE http://localhost:8000/ai/chat/delete/conv-550e8400-e29b-41d4-a716-446655440000/ \
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

## 文件分析接口（新版 - 推荐）

新版分析接口采用三步走流程，提供更灵活的文件管理：
1. 创建分析会话
2. 上传文件（可多次上传）
3. 开始分析

### 8. 创建分析会话

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/session/create/`
- **认证**: 是
- **描述**: 创建一个新的分析会话（第一步）

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| analysis_type | string | 否 | 分析类型：`personal`(个人)或`company`(企业)，默认 `personal` |
| title | string | 否 | 会话标题，默认 "新分析" |

**分析类型说明**:
- `personal`: 个人分析模式 - 消耗1配额
- `company`: 企业分析模式 - 消耗2配额

### 请求示例
```bash
# JSON格式
curl -X POST http://localhost:8000/ai/analyze/session/create/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_type": "personal",
    "title": "销售数据分析"
  }'

# 表单格式
curl -X POST http://localhost:8000/ai/analyze/session/create/ \
  -H "Authorization: Bearer <token>" \
  -F "analysis_type=company" \
  -F "title=Q4业务分析报告"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "分析会话已创建",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-uuid",
    "analysis_type": "personal",
    "title": "销售数据分析",
    "model": "doubao",
    "created_at": "2026-01-22T10:00:00Z"
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | analysis_type参数错误（必须是personal或company） |
| 401 | 未登陆 |

---

### 9. 上传分析文件

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/session/<session_id>/upload/`
- **认证**: 是
- **描述**: 上传文件到分析会话（第二步，可多次调用）

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话ID（URL路径参数） |
| files | file | 是 | 要上传的文件（支持多个） |

**支持的文件格式**: PDF、Word、Excel、文本文件等（最大50MB）

### 请求示例
```bash
# 单次上传多个文件
curl -X POST http://localhost:8000/ai/analyze/session/550e8400-xxx/upload/ \
  -H "Authorization: Bearer <token>" \
  -F "files=@/path/to/file1.pdf" \
  -F "files=@/path/to/file2.xlsx" \
  -F "files=@/path/to/file3.docx"

# 多次上传（灵活追加文件）
curl -X POST http://localhost:8000/ai/analyze/session/550e8400-xxx/upload/ \
  -H "Authorization: Bearer <token>" \
  -F "files=@/path/to/additional_file.pdf"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "文件已上传",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "uploaded_count": 3,
    "total_count": 3,
    "uploaded_files": [
      {
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/550e8400-xxx/abc123.pdf",
        "original_name": "年度报告2025.pdf"
      },
      {
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/550e8400-xxx/def456.xlsx",
        "original_name": "销售数据.xlsx"
      },
      {
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/550e8400-xxx/ghi789.docx",
        "original_name": "分析文档.docx"
      }
    ]
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 未选择文件、文件格式不支持或文件过大 |
| 401 | 未登陆 |
| 404 | 会话不存在或无权访问 |

---

### 10. 开始初次分析

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/session/<session_id>/start/`
- **认证**: 是
- **描述**: 基于已上传的所有文件开始分析（第三步，使用内置提示词）

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话ID（URL路径参数） |

**注意事项**:
- 此接口会扣除用户配额（personal=1，company=2）
- 必须先通过上传接口上传至少一个文件
- 每个会话只能调用一次 start 接口，后续使用 continue 接口追问

### 请求示例
```bash
curl -X POST http://localhost:8000/ai/analyze/session/550e8400-xxx/start/ \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 流式 SSE 响应
```
event: start
data: {"session_id":"550e8400-xxx","status":"started","analysis_type":"personal","file_count":3}

event: progress
data: {"stage":"first_token","elapsed_ms":1234}

event: message
data: {"message":"根据您上传的3个文件，我进行了以下分析..."}

event: message
data: {"message":"### 数据总结\n\n1. ..."}

event: end
data: {"status":"completed","quota_cost":1}
```

**响应后数据结构**：
```json
{
  "messages": [
    {
      "role": "user",
      "content": "[已上传3个文件，开始分析]",
      "files": [
        {
          "path": "~/path/to/file1.pdf",
          "original_name": "年度报告2025.pdf"
        },
        {
          "path": "~/path/to/file2.xlsx",
          "original_name": "销售数据.xlsx"
        }
      ]
    },
    {
      "role": "assistant",
      "content": "根据您上传的文件，我进行了以下分析..."
    }
  ]
}
```

**特殊说明**：
- 用户消息使用固定文本 `[已上传N个文件，开始分析]`，而不是保存内置系统提示词
- 所有初始上传的文件都关联到这条用户消息的 `files` 字段

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 会话中没有文件，或该会话已经开始过分析 |
| 401 | 未登陆 |
| 402 | 配额不足 |
| 404 | 会话不存在或无权访问 |

---

### 11. 继续分析（追问）

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/session/<session_id>/continue/`
- **认证**: 是
- **描述**: 在分析会话中继续追问，支持上传新文件

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话ID（URL路径参数） |
| prompt | string | 是 | 追问内容 |
| files | file | 否 | 新增文件（可选） |

**注意事项**：
- 每次调用都会扣除配额
- 可以在追问时上传新文件，新文件会关联到当前用户消息

### 请求示例
```bash
# 纯文本追问
curl -X POST http://localhost:8000/ai/analyze/session/550e8400-xxx/continue/ \
  -H "Authorization: Bearer <token>" \
  -F "prompt=请针对第二部分的数据再做深入分析"

# 追问并上传新文件
curl -X POST http://localhost:8000/ai/analyze/session/550e8400-xxx/continue/ \
  -H "Authorization: Bearer <token>" \
  -F "prompt=请将这个新数据与之前的对比分析" \
  -F "files=@/path/to/new_file.csv"
```

### 返回数据类型

#### 流式 SSE 响应
```
event: start
data: {"session_id":"550e8400-xxx","status":"started"}

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
| 400 | prompt不能为空 |
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
      
      // 支持新的对象格式和旧的字符串格式
      let fileName, filePath;
      if (typeof file === 'object') {
        // 新格式：{path: "...", original_name: "..."}
        fileName = file.original_name;
        filePath = file.path;
      } else {
        // 旧格式：直接是路径字符串
        fileName = file.split('/').pop();
        filePath = file;
      }
      
      attachmentItem.innerHTML = `
        <span class="attachment-icon">📎</span>
        <span class="attachment-name">${fileName}</span>
      `;
      attachmentItem.dataset.filePath = filePath;  // 保存路径供下载/预览使用
      attachmentsDiv.appendChild(attachmentItem);
    });
    
    messageDiv.appendChild(attachmentsDiv);
  }
  
  // 添加到聊天容器
  document.getElementById('chat-container').appendChild(messageDiv);
}

// 发送带附件的消息示例
async function sendMessageWithFiles(conversationId, prompt, files) {
  const formData = new FormData();
  formData.append('prompt', prompt);
  
  // 添加多个文件
  files.forEach(file => {
    formData.append('files', file);
  });
  
  const response = await fetch(`/ai/chat/continue/${conversationId}/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
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
| DOCX | Word文档 | 50MB |
| DOC | Word 97-2003 | 50MB |
| XLSX | Excel电子表格 | 50MB |
| XLS | Excel 97-2003 | 50MB |
| CSV | 逗号分隔值 | 50MB |
| TXT | 纯文本 | 50MB |
| MD | Markdown | 50MB |
| JSON | JSON数据 | 50MB |

---

## 常见错误处理

| 错误 | 原因 | 解决方案 |
|------|------|--------|
| 401 未登陆 | token无效或过期 | 重新调用登陆接口获取有效token |
| 404 会话不存在 | 会话ID错误或已删除 | 检查会话ID或创建新会话 |
| 400 文件不支持 | 上传的文件格式不支持 | 上传支持的文件格式 |
| 500 服务器错误 | 服务器内部错误 | 稍后重试或联系技术支持 |

---

## 版本历史

| 版本 | 日期 | 更新说明 |
|------|------|--------|
| 1.3 | 2026-01-22 | **重要更新**：拆分分析接口为三步流程，支持灵活的文件管理。新增 `/analyze/session/create/` 创建会话、`/analyze/session/<session_id>/upload/` 上传文件（可多次调用）、`/analyze/session/<session_id>/start/` 开始分析。初始分析使用固定文本 "[已上传N个文件，开始分析]" 替代内置提示词；新增 SSE `progress` 事件，返回首字节延迟（毫秒），便于前端显示进度。旧接口 `/analyze/new/` 仍然保留用于兼容 |
| 1.2 | 2026-01-22 | **重要更新**：优化文件关联机制，文件对象现在包含 `path` 和 `original_name` 两个字段，前端可以显示原始文件名。新格式为 `{path: "...", original_name: "..."}`，支持向后兼容旧的字符串路径格式 |
| 1.1 | 2026-01-22 | 优化附件关联机制，文件现在关联到具体的用户消息中（`messages[].files`），方便前端准确展示。保留会话级别的 `files` 数组用于向后兼容 |
| 1.0 | 2026-01-17 | 初始版本，包含17个AI相关接口 |
