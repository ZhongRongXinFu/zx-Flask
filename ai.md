# AI 接口 API 文档

**更新时间**: 2026年1月17日

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
        "content": "你好，请帮我分析一下这个文件"
      },
      {
        "role": "assistant",
        "content": "好的，请上传文件后我会为您分析。"
      }
    ],
    "files": [
      "~/Desktop/zhongxin/flask/static/chat-uploads/conv-xxx/file1.pdf"
    ],
    "created_at": "2026-01-17T10:00:00Z",
    "updated_at": "2026-01-17T15:30:00Z"
  }
}
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
- **路由**: `/ai/conversation/<conversation_id>/title/`
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

## 文件分析接口

## 8. 初始化分析会话

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/init/`
- **认证**: 是
- **描述**: 初始化一个多文件分析会话，支持个人和企业两种分析模式

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| use | string | 否 | 分析模式：`personal`(个人)或`company`(企业)，默认 `personal` |
| title | string | 否 | 会话标题，默认 "文件分析会话" |

**分析模式说明**:
- `personal`: 个人分析模式 - 提取关键信息，进行数据分析，给出专业建议
- `company`: 企业分析模式 - 企业级专业顾问分析，包括执行摘要、详细分析、风险评估等

### 请求示例
```bash
# 创建个人分析会话
curl -X POST http://localhost:8000/ai/analyze/init/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "use": "personal",
    "title": "销售数据分析"
  }'

# 创建企业分析会话
curl -X POST http://localhost:8000/ai/analyze/init/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "use": "company",
    "title": "Q4业务分析报告"
  }'
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "会话已初始化",
  "data": {
    "session_id": "session-550e8400-e29b-41d4-a716-446655440000",
    "conversation_id": "session-550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-uuid",
    "use": "personal",
    "title": "销售数据分析",
    "files": [],
    "file_details": [],
    "created_at": "2026-01-17T10:00:00Z",
    "updated_at": "2026-01-17T10:00:00Z"
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | use参数错误（必须是personal或company） |
| 401 | 未登陆 |

---

## 9. 上传文件到分析会话

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/<session_id>/upload/`
- **认证**: 是
- **描述**: 上传文件到分析会话，支持多文件上传

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 分析会话ID |
| files | file | 是 | 要上传的文件（支持多个） |

**支持的文件格式**: PDF、Word、Excel、文本文件等

### 请求示例
```bash
curl -X POST http://localhost:8000/ai/analyze/session-xxx/upload/ \
  -H "Authorization: Bearer <token>" \
  -F "files=@/path/to/file1.pdf" \
  -F "files=@/path/to/file2.docx" \
  -F "files=@/path/to/file3.xlsx"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "文件已上传",
  "data": {
    "session_id": "session-550e8400-e29b-41d4-a716-446655440000",
    "files_uploaded": 3,
    "total_files": 3,
    "file_list": [
      {
        "filename": "report.pdf",
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/session-xxx/abc123.pdf",
        "size": 2048576,
        "uploaded_at": "2026-01-17T10:15:00Z"
      },
      {
        "filename": "data.xlsx",
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/session-xxx/def456.xlsx",
        "size": 1024000,
        "uploaded_at": "2026-01-17T10:15:05Z"
      }
    ]
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 未选择文件或文件格式不支持 |
| 401 | 未登陆 |
| 404 | 分析会话不存在 |

---

## 10. 执行分析

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/<session_id>/execute/`
- **认证**: 是
- **描述**: 执行文件分析，基于上传的文件进行AI分析（流式响应）

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 分析会话ID |
| model | string | 否 | AI模型：`deepseek`或`doubao`，默认 `deepseek` |
| custom_instruction | string | 否 | 自定义分析指示，附加到系统提示词后 |

### 请求示例
```bash
# 基础分析
curl -X POST http://localhost:8000/ai/analyze/session-xxx/execute/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek",
    "custom_instruction": "请重点关注成本控制部分"
  }'
```

### 返回数据类型

#### 流式 SSE 响应
```
event: start
data: {"session_id":"session-xxx","file_count":3,"use":"personal","status":"started"}

event: message
data: {"content":"### 分析结果\n\n根据上传的三个文件..."}

event: message
data: {"content":"## 数据总结\n- 总销售额：..."}

event: end
data: {"status":"completed","conversation_id":"session-xxx"}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | 会话中没有文件或模型参数错误 |
| 401 | 未登陆 |
| 404 | 分析会话不存在 |

---

## 11. 继续分析（多轮追问）

### 接口信息
- **方法**: `POST`
- **路由**: `/ai/analyze/<session_id>/continue/`
- **认证**: 是
- **描述**: 在分析会话中继续追问，支持多轮对话

### 请求参数

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 分析会话ID |
| prompt | string | 是 | 追问内容 |
| files | file | 否 | 新增文件（可选） |

### 请求示例
```bash
# 继续追问
curl -X POST http://localhost:8000/ai/analyze/session-xxx/continue/ \
  -H "Authorization: Bearer <token>" \
  -F "prompt=请针对第二部分的数据再做深入分析"

# 追问并上传新文件
curl -X POST http://localhost:8000/ai/analyze/session-xxx/continue/ \
  -H "Authorization: Bearer <token>" \
  -F "prompt=请将这个新数据与之前的对比分析" \
  -F "files=@/path/to/new_file.csv"
```

### 返回数据类型

#### 流式 SSE 响应
```
event: start
data: {"session_id":"session-xxx","status":"started"}

event: message
data: {"content":"根据您的追问，我进行了深入分析..."}

event: end
data: {"status":"completed"}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 400 | prompt不能为空 |
| 401 | 未登陆 |
| 404 | 分析会话不存在或无权访问 |

---

## 12. 获取分析会话信息

### 接口信息
- **方法**: `GET`
- **路由**: `/ai/analyze/<session_id>/`
- **认证**: 是
- **描述**: 获取分析会话的详细信息

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| session_id | string | URL路径 | 是 | 分析会话ID |

### 请求示例
```bash
curl -X GET http://localhost:8000/ai/analyze/session-xxx/ \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "data": {
    "session_id": "session-550e8400-e29b-41d4-a716-446655440000",
    "conversation_id": "session-550e8400-e29b-41d4-a716-446655440000",
    "use": "personal",
    "title": "销售数据分析",
    "files": [
      {
        "filename": "report.pdf",
        "path": "~/Desktop/zhongxin/flask/static/chat-uploads/session-xxx/abc123.pdf",
        "size": 2048576,
        "uploaded_at": "2026-01-17T10:15:00Z"
      }
    ],
    "messages": [
      {
        "role": "user",
        "content": "请分析这些文件"
      },
      {
        "role": "assistant",
        "content": "我已经分析了您上传的文件..."
      }
    ],
    "created_at": "2026-01-17T10:00:00Z",
    "updated_at": "2026-01-17T10:30:00Z"
  }
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 401 | 未登陆 |
| 404 | 分析会话不存在或无权访问 |

---

## 13. 删除分析会话

### 接口信息
- **方法**: `DELETE`
- **路由**: `/ai/analyze/<session_id>/`
- **认证**: 是
- **描述**: 删除分析会话及其所有关联文件

### 请求参数

| 参数 | 类型 | 位置 | 必须 | 说明 |
|------|------|------|------|------|
| session_id | string | URL路径 | 是 | 分析会话ID |

### 请求示例
```bash
curl -X DELETE http://localhost:8000/ai/analyze/session-xxx/ \
  -H "Authorization: Bearer <token>"
```

### 返回数据类型

#### 成功（200）
```json
{
  "code": 0,
  "message": "会话已删除"
}
```

#### 错误响应

| 错误码 | 说明 |
|-------|------|
| 401 | 未登陆 |
| 404 | 分析会话不存在或无权访问 |

---

## 兑换码管理接口

## 14. 创建兑换码（管理员）

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

## 15. 兑换配额

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

## 16. 查看兑换码列表（管理员）

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
| 1.0 | 2026-01-17 | 初始版本，包含17个AI相关接口 |
