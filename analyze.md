# AI 文件分析接口完整文档

## 概述

`/analyze` 系列接口提供了一套完整的多文件分析功能，支持：
- 初始化分析会话
- 上传和管理分析文件
- 执行文件分析
- 多轮交互和追问
- 会话信息获取和管理

所有接口都需要进行身份验证（需要有效的登录令牌）。

---

## 分析模式

系统支持两种分析模式：

### 1. Personal（个人分析模式）
用于个人用户分析文件，提供通俗易懂的分析：
- 提取关键信息和数据
- 进行数据分析和趋势判断
- 给出专业建议
- 用简洁语言解释概念

### 2. Company（企业分析模式）
用于企业级分析，提供战略性咨询：
- 全面的数据分析和商业价值评估
- 关键业务指标和风险点识别
- 战略性建议和优化方案
- 包含 Executive Summary、详细分析、关键指标、风险评估、建议方案和实施计划

---

## API 接口详解

### 1. 初始化分析会话

**请求**
```http
POST /ai/analyze/init/
Content-Type: application/json
Authorization: Bearer {token}

{
  "use": "personal",           // 可选，default: "personal"，取值: "personal" | "company"
  "title": "财务报表分析"      // 可选，default: "文件分析会话"
}
```

**响应**
```json
{
  "code": 0,
  "message": "会话已初始化",
  "data": {
    "session_id": "ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45",
    "conversation_id": "ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45",
    "user_id": "user-uuid-123",
    "use": "personal",
    "title": "财务报表分析",
    "files": [],
    "file_details": [],
    "created_at": "2026-01-18T10:30:00.123456",
    "updated_at": "2026-01-18T10:30:00.123456"
  }
}
```

**状态码**
- `0`: 成功
- `400`: use 参数无效
- `500`: 初始化失败

**说明**
- 返回的 `session_id` 和 `conversation_id` 值相同，用于后续操作
- 初始化时不包含任何文件
- 默认使用 deepseek 模型

---

### 2. 上传文件到分析会话

**请求**
```http
POST /ai/analyze/{session_id}/upload/
Content-Type: multipart/form-data
Authorization: Bearer {token}

[文件内容]
参数名: files[] (支持多文件)
```

**响应**
```json
{
  "code": 0,
  "message": "文件已上传",
  "data": {
    "session_id": "ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45",
    "files_uploaded": 2,
    "total_files": 2,
    "file_list": [
      {
        "filename": "财务报表.xlsx",
        "path": "/path/to/file1.xlsx",
        "size": 1024576,
        "uploaded_at": "2026-01-18T10:31:00.123456"
      },
      {
        "filename": "员工名单.pdf",
        "path": "/path/to/file2.pdf",
        "size": 2048576,
        "uploaded_at": "2026-01-18T10:31:05.123456"
      }
    ]
  }
}
```

**状态码**
- `0`: 成功
- `400`: 文件格式/大小错误或未选择文件
- `404`: 分析会话不存在
- `500`: 上传失败

**支持的文件格式**
```
文档: .pdf, .txt, .md, .doc, .docx, .xlsx, .xls, .csv
图片: .jpg, .jpeg, .png, .gif, .bmp
数据: .json, .xml, .sql
压缩: .zip, .rar, .7z, .tar, .gz
```

**文件限制**
- 单个文件最大 50MB
- 单次上传最多 10 个文件
- 会话总文件数上限 100 个

**说明**
- 支持多次上传，文件会累加到会话中
- 文件保存在服务器的 `static/chat-uploads/{session_id}/` 目录
- 每个文件生成唯一的随机名称保存
- 返回的 `file_list` 包含所有已上传文件的详情

---

### 3. 执行分析

**请求**
```http
POST /ai/analyze/{session_id}/execute/
Content-Type: application/json
Authorization: Bearer {token}

{
  "model": "deepseek",                    // 可选，取值: "deepseek" | "doubao"
  "custom_instruction": "重点关注成本控制" // 可选，补充分析说明
}
```

**响应** (Server-Sent Events - 流式响应)
```
event: start
data: {"session_id":"ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45","file_count":2,"use":"personal","status":"started"}

event: message
data: {"content":"根据您上传的财务报表..."}

event: message
data: {"content":"主要分析结果如下："}

...更多消息...

event: end
data: {"status":"completed","conversation_id":"ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45"}

event: error
data: {"status":"error","message":"错误描述"}
```

**事件类型说明**
- `start`: 分析开始，包含会话 ID、文件数量和分析模式
- `message`: 分析内容流，逐块返回 AI 的分析结果
- `end`: 分析完成，返回会话 ID
- `error`: 发生错误，返回错误信息

**状态码**
- `200`: 流式连接成功
- `400`: 参数错误（模型不支持等）或会话中无文件
- `404`: 分析会话不存在
- `500`: 分析失败

**说明**
- 返回 `text/event-stream` 格式的流式响应
- 需要在客户端侦听 SSE 事件处理
- `custom_instruction` 会追加到标准分析提示词后面
- 分析过程中的所有对话会自动保存到数据库
- 前置条件：会话中必须至少有一个文件

**JavaScript 客户端示例**
```javascript
const eventSource = new EventSource('/ai/analyze/{session_id}/execute/', {
  headers: {'Authorization': 'Bearer ' + token}
});

eventSource.addEventListener('start', (e) => {
  const data = JSON.parse(e.data);
  console.log(`开始分析 ${data.file_count} 个文件...`);
});

eventSource.addEventListener('message', (e) => {
  const data = JSON.parse(e.data);
  console.log('分析内容:', data.content);
  // 更新 UI 显示分析结果
});

eventSource.addEventListener('end', (e) => {
  const data = JSON.parse(e.data);
  console.log('分析完成');
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  const data = JSON.parse(e.data);
  console.error('分析出错:', data.message);
  eventSource.close();
});
```

---

### 4. 继续分析（多轮追问）

**请求**
```http
POST /ai/analyze/{session_id}/continue/
Content-Type: application/x-www-form-urlencoded 或 multipart/form-data
Authorization: Bearer {token}

参数:
  prompt=进一步分析产品成本结构   // 必需
  files[]=file1                   // 可选，可追加新文件
  files[]=file2
```

**响应** (Server-Sent Events - 流式响应)
```
event: start
data: {"session_id":"ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45","status":"started"}

event: message
data: {"content":"基于前面的分析..."}

...更多消息...

event: end
data: {"status":"completed"}

event: error
data: {"status":"error","message":"错误描述"}
```

**状态码**
- `200`: 流式连接成功
- `400`: 提示词为空或文件上传失败
- `404`: 分析会话不存在
- `500`: 处理失败

**说明**
- 继承前一轮的对话历史和已上传文件
- 支持上传新的文件，新文件会追加到已有文件列表中
- 新的提示词和回复都会保存到数据库
- 返回流式响应，需要客户端侦听 SSE 事件
- 前置条件：会话必须存在且已执行过初始分析

**多轮对话流程**
```
1. POST /analyze/init/              # 初始化会话
2. POST /analyze/{id}/upload/       # 上传文件
3. POST /analyze/{id}/execute/      # 执行初始分析
4. POST /analyze/{id}/continue/     # 第一次追问
5. POST /analyze/{id}/continue/     # 第二次追问
... 循环进行多轮交互
```

---

### 5. 获取分析会话信息

**请求**
```http
GET /ai/analyze/{session_id}/
Authorization: Bearer {token}
```

**响应**
```json
{
  "code": 0,
  "data": {
    "session_id": "ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45",
    "conversation_id": "ed8eeb9d-d3b9-4b4d-9c39-2853d3efab45",
    "use": "personal",
    "title": "财务报表分析",
    "files": [
      {
        "filename": "财务报表.xlsx",
        "path": "/path/to/file1.xlsx",
        "size": 1024576,
        "uploaded_at": "2026-01-18T10:31:00.123456"
      }
    ],
    "messages": [
      {
        "role": "user",
        "content": "【个人分析模式】..."
      },
      {
        "role": "assistant",
        "content": "根据您上传的财务报表..."
      },
      {
        "role": "user",
        "content": "进一步分析产品成本结构"
      },
      {
        "role": "assistant",
        "content": "基于前面的分析..."
      }
    ],
    "created_at": "2026-01-18T10:30:00.123456",
    "updated_at": "2026-01-18T10:32:30.123456"
  }
}
```

**状态码**
- `0`: 成功
- `404`: 分析会话不存在或无权访问
- `500`: 获取失败

**说明**
- 返回完整的会话信息，包括所有消息历史
- `messages` 数组记录了所有用户提示和 AI 回复
- `files` 包含所有文件的元数据
- 可用于恢复或继续之前的分析对话

---

### 6. 删除分析会话

**请求**
```http
DELETE /ai/analyze/{session_id}/
Authorization: Bearer {token}
```

**响应**
```json
{
  "code": 0,
  "message": "会话已删除"
}
```

**状态码**
- `0`: 成功
- `404`: 分析会话不存在
- `500`: 删除失败

**说明**
- 删除会话记录和所有关联文件
- 会从数据库中彻底移除
- 会从磁盘上删除上传的文件和目录
- 删除后无法恢复，请谨慎操作

---

## 完整使用流程示例

### 场景：分析公司财务报表和员工结构

**步骤 1: 初始化会话**
```bash
curl -X POST http://localhost:5000/ai/analyze/init/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{
    "use": "company",
    "title": "2025年度财务和组织分析"
  }'

# 响应: {"code": 0, "data": {"session_id": "abc-123-def", ...}}
```

**步骤 2: 上传财务报表**
```bash
curl -X POST http://localhost:5000/ai/analyze/abc-123-def/upload/ \
  -H "Authorization: Bearer your_token" \
  -F "files=@财务报表.xlsx" \
  -F "files=@成本明细.csv"

# 响应: {"code": 0, "data": {"files_uploaded": 2, "total_files": 2, ...}}
```

**步骤 3: 执行初始分析**
```bash
curl -X POST http://localhost:5000/ai/analyze/abc-123-def/execute/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{
    "model": "deepseek",
    "custom_instruction": "重点分析成本控制和利润率趋势"
  }'

# 响应: 流式 SSE 数据
# event: start
# event: message
# event: message
# ...
# event: end
```

**步骤 4: 追问分析**
```bash
curl -X POST http://localhost:5000/ai/analyze/abc-123-def/continue/ \
  -H "Authorization: Bearer your_token" \
  -d "prompt=请给出降低成本的具体建议&files=@员工名单.xlsx"

# 响应: 流式 SSE 数据
```

**步骤 5: 获取完整会话信息**
```bash
curl http://localhost:5000/ai/analyze/abc-123-def/ \
  -H "Authorization: Bearer your_token"

# 响应: {"code": 0, "data": {...所有消息和文件信息...}}
```

**步骤 6: 删除会话（使用完后）**
```bash
curl -X DELETE http://localhost:5000/ai/analyze/abc-123-def/ \
  -H "Authorization: Bearer your_token"

# 响应: {"code": 0, "message": "会话已删除"}
```

---

## 错误处理

### 常见错误和解决方案

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `404 分析会话不存在` | session_id 错误或会话已删除 | 检查 session_id，重新初始化会话 |
| `400 不是分析会话` | 会话类型不匹配（普通对话 vs 分析会话） | 确保使用正确的会话 ID |
| `400 未选择文件` | upload 时没有发送文件 | 使用 `files[]` 参数上传文件 |
| `400 会话中没有文件` | execute 前未上传文件 | 先调用 upload 接口上传文件 |
| `400 提示词不能为空` | continue 时 prompt 为空 | 提供有效的 prompt 参数 |
| `400 文件格式错误` | 上传的文件格式不支持 | 上传支持的文件格式 |
| `500 执行分析失败` | AI 模型调用出错 | 检查服务器日志，重试 |

### 响应格式说明

**成功响应**
```json
{
  "code": 0,
  "message": "操作说明",
  "data": {...}
}
```

**错误响应**
```json
{
  "code": 400,           // 或 404, 500 等
  "message": "错误描述"
}
```

---

## 数据模型

### 会话对象 (Conversation)

```python
{
  "id": str,              # 会话 ID (UUID)
  "user_id": str,         # 用户 ID (UUID)
  "model": str,           # 使用的模型 ("deepseek" | "doubao")
  "title": str,           # 会话标题
  "analysis_type": str,   # 分析类型 ("personal" | "company")
  "messages": list,       # 消息列表 [{role, content}, ...]
  "files": list,          # 文件路径列表
  "file_details": list,   # 文件详情列表 [{filename, path, size, uploaded_at}, ...]
  "created_at": str,      # 创建时间 (ISO 8601)
  "updated_at": str       # 更新时间 (ISO 8601)
}
```

### 消息对象 (Message)

```python
{
  "role": str,     # "user" | "assistant"
  "content": str   # 消息内容
}
```

### 文件详情对象 (FileDetail)

```python
{
  "filename": str,     # 原始文件名
  "path": str,         # 服务器上的完整路径
  "size": int,         # 文件大小 (字节)
  "uploaded_at": str   # 上传时间 (ISO 8601)
}
```

---

## 性能优化建议

1. **流式处理响应**：使用 EventSource 或其他 SSE 客户端库处理流式响应，而不是等待整个响应完成

2. **批量上传**：在一次 upload 请求中上传多个文件，减少网络往返次数

3. **会话复用**：不要频繁初始化新会话，尽量复用已有会话进行多轮对话

4. **文件管理**：分析完成后及时删除不需要的会话，释放服务器存储空间

5. **超时设置**：客户端应设置合理的超时时间（建议 30-60 秒以上），因为分析可能需要较长时间

---

## 安全说明

1. **身份验证**：所有接口都需要有效的认证令牌，通过 `Authorization: Bearer {token}` 传递

2. **权限隔离**：用户只能访问自己的分析会话，系统通过 user_id 验证权限

3. **文件验证**：上传的文件会进行格式和大小验证，防止恶意文件上传

4. **数据隐私**：会话数据存储在数据库中，文件存储在服务器磁盘，请确保有适当的安全措施

5. **速率限制**：建议对 API 接口实施速率限制，防止滥用

---

## 技术细节

### 数据库存储

- **表**: `conversations`
- **字段**:
  - `id`: 主键，会话 ID
  - `user_id`: 用户 ID，用于权限控制
  - `model`: 使用的 AI 模型
  - `title`: 会话标题
  - `analysis_type`: 分析类型（NULL 表示普通对话）
  - `messages`: JSON，消息历史
  - `files`: JSON，文件路径列表
  - `file_details`: JSON，文件元数据列表
  - `created_at`: 创建时间
  - `updated_at`: 更新时间

### 文件存储位置

```
{PRODUCT_IMAGE_DIR}/chat-uploads/{session_id}/{uuid}.{ext}
```

例如:
```
~/Desktop/zhongxin/flask/static/chat-uploads/abc-123-def/a1b2c3d4e5f6g7h8.xlsx
```

### 支持的 AI 模型

- **deepseek**: 默认模型，性能均衡
- **doubao**: 字节跳动豆包大模型，快速响应

---

## 常见问题

**Q: 一个会话最多可以上传多少文件？**
A: 理论上无限制，但建议不超过 100 个文件，以确保分析质量

**Q: 会话数据保存多久？**
A: 无时间限制，除非用户主动删除或管理员清理

**Q: 能否同时运行多个分析？**
A: 可以，每个会话是独立的，可以并行处理多个分析请求

**Q: 分析过程中可否中断？**
A: 可以，关闭客户端连接会中断流式响应，但已收到的数据会保存

**Q: 支持哪些文件格式？**
A: 支持 PDF、Word、Excel、CSV、TXT、JSON、XML 等常见文件格式（详见文件限制章节）

**Q: 分析结果的准确性如何保证？**
A: 系统使用专业的 AI 模型和精心设计的提示词，用户可通过 custom_instruction 优化分析方向

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0 | 2026-01-18 | 初始版本，支持基础的文件分析功能 |

---

## 联系与支持

如有问题或建议，请联系技术支持团队。
