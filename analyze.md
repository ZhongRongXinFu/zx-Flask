# 数据分析接口文档

## 概述

数据分析模块为用户提供两种数据分析方式：**个人分析**和**企业分析**。两种分析模式都使用内置的专业提示词，能够为用户提供针对性的分析建议。

### 关键特性

- **两种分析模式**：个人分析（1点/次）、企业分析（2点/次）
- **内置提示词**：首次分析使用系统内置的专业提示词，无需用户提供
- **流式响应**：使用 SSE（Server-Sent Events）实时返回分析结果
- **文件管理**：首次分析必须上传文件，后续对话可追加新文件和自定义提示词
- **积分管理**：自动扣除分析消耗的积分，余额不足时直接拒绝
- **多轮对话**：支持基于初始分析文件的多轮交互

### 典型使用流程

1. 用户上传文件 → **POST /analyze/new/** → 系统使用内置提示词进行分析（返回 SSE 流）
2. 用户追问 → **POST /analyze/continue/{id}/** → 可携带新文件和自定义提示词（返回 SSE 流）

---

## 接口总览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/ai/analyze/new/` | POST | 创建新的分析会话（必须上传文件） |
| `/ai/analyze/continue/<id>/` | POST | 继续分析对话（可追加文件和提示词） |
| `/ai/analyze/list/` | GET | 获取用户的所有分析对话 |
| `/ai/analyze/get/<id>/` | GET | 获取分析对话详情 |
| `/ai/analyze/delete/<id>/` | DELETE | 删除分析对话 |
| `/ai/analyze/quota/` | GET | 获取用户配额信息 |

---

## 1. 创建新的分析会话

### 请求

```
POST /ai/analyze/new/
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `analysis_type` | string | 否 | 分析类型，`personal`（个人分析，默认）或 `company`（企业分析） |
| `title` | string | 否 | 会话标题，默认为"新分析" |
| `files` | file | **是** | 上传的分析文件（单个或多个），支持的格式：txt, pdf, docx, xlsx, csv, json 等 |

**重要说明**：
- 分析模块的 AI 模型固定为**豆包（doubao）**，无需指定
- **首次分析必须上传文件**，系统会使用内置的专业提示词进行分析
- 不需要提供 `custom_instruction`，系统根据 `analysis_type` 自动使用对应的内置提示词

### 响应

#### 成功：返回 SSE 流

```
event: start
data: {"conversation_id": "uuid", "status": "started", "analysis_type": "personal"}

event: message
data: {"message": "分析内容第1段..."}

event: message
data: {"message": "分析内容第2段..."}

event: end
data: {"status": "completed", "quota_cost": 1}
```

#### 失败：积分不足

```json
{
  "code": 402,
  "message": "配额不足",
  "data": {
    "required": 1,
    "current": 0
  }
}
```

#### 失败：未上传文件

```json
{
  "code": 400,
  "message": "初始分析必须上传至少一个文件"
}
```

### 示例

#### cURL

```bash
# 创建并开始个人分析（使用内置提示词）
curl -X POST "http://localhost:8000/ai/analyze/new/" \
  -H "Authorization: Bearer your_token" \
  -F "analysis_type=personal" \
  -F "title=销售数据分析" \
  -F "files=@sales_data.xlsx"

# 创建企业分析
curl -X POST "http://localhost:8000/ai/analyze/new/" \
  -H "Authorization: Bearer your_token" \
  -F "analysis_type=company" \
  -F "title=战略规划分析" \
  -F "files=@strategic_plan.pdf"
```

#### JavaScript (小程序)

```javascript
// 上传文件并开始分析
wx.uploadFile({
  url: 'http://api.example.com/ai/analyze/new/',
  filePath: tempFilePath, // 从 wx.chooseImage/wx.chooseMessageFile 获取的文件路径
  name: 'files',
  formData: {
    analysis_type: 'personal',
    title: '销售数据分析'
  },
  header: {
    'Authorization': `Bearer ${token}`
  },
  success: (res) => {
    // 处理 SSE 流响应（见下文）
    const data = JSON.parse(res.data);
    handleAnalysisStream(data);
  }
});
```

---

## 2. 继续分析对话

在初始分析完成后，可以基于已分析的文件继续提问或上传新文件。

### 请求

```
POST /ai/analyze/continue/<conversation_id>/
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `prompt` | string | 是 | 用户的追问或自定义指示 |
| `files` | file | 否 | 新上传的文件（可选），会追加到原有文件列表 |

**说明**：在继续分析时，用户可以：
- 仅提供提示词（追问问题）
- 提供提示词 + 新文件（追加数据进行分析）

### 响应

与创建新会话类似，返回 SSE 流：

```
event: start
data: {"conversation_id": "uuid", "status": "started"}

event: message
data: {"message": "进一步分析内容..."}

event: end
data: {"status": "completed", "quota_cost": 1}
```

### 示例

#### cURL

```bash
# 仅追问
curl -X POST "http://localhost:8000/ai/analyze/continue/uuid/" \
  -H "Authorization: Bearer your_token" \
  -F "prompt=请基于上面的分析，给出改进建议"

# 追问 + 上传新文件
curl -X POST "http://localhost:8000/ai/analyze/continue/uuid/" \
  -H "Authorization: Bearer your_token" \
  -F "prompt=请结合新上传的财务数据重新分析" \
  -F "files=@financial_data.xlsx"
```

#### JavaScript (小程序)

```javascript
// 方式1：仅追问（不上传新文件）
wx.request({
  url: `http://api.example.com/ai/analyze/continue/${conversationId}/`,
  method: 'POST',
  header: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/x-www-form-urlencoded'
  },
  data: {
    prompt: '请基于上面的分析，给出改进建议'
  },
  success: (res) => {
    handleAnalysisStream(res);
  }
});

// 方式2：追问 + 上传新文件
wx.uploadFile({
  url: `http://api.example.com/ai/analyze/continue/${conversationId}/`,
  filePath: tempFilePath, // 新文件路径
  name: 'files',
  formData: {
    prompt: '请结合新上传的财务数据重新分析'
  },
  header: {
    'Authorization': `Bearer ${token}`
  },
  success: (res) => {
    handleAnalysisStream(res);
  }
});
```

---

## 3. SSE 流处理

分析接口返回的是 SSE（Server-Sent Events）流，需要在前端进行相应处理。

### 事件类型

| 事件 | 说明 | 数据结构 |
|------|------|--------|
| `start` | 分析开始 | `{conversation_id, status, analysis_type(新分析时)}` |
| `message` | 分析内容块 | `{message: string}` |
| `end` | 分析完成 | `{status, quota_cost}` |
| `error` | 分析出错 | `{status, message}` |

### 前端处理示例

#### JavaScript（原生 EventSource）

```javascript
function handleAnalysisStream(url, token) {
  const eventSource = new EventSource(url, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  let fullResponse = '';

  eventSource.addEventListener('start', (e) => {
    const data = JSON.parse(e.data);
    console.log('分析开始:', data);
  });

  eventSource.addEventListener('message', (e) => {
    const data = JSON.parse(e.data);
    fullResponse += data.message;
    // 更新 UI，显示实时内容
    updateUI(fullResponse);
  });

  eventSource.addEventListener('end', (e) => {
    const data = JSON.parse(e.data);
    console.log('分析完成，消耗:', data.quota_cost);
    eventSource.close();
  });

  eventSource.addEventListener('error', (e) => {
    const data = JSON.parse(e.data);
    console.error('分析出错:', data.message);
    eventSource.close();
  });
}
```

#### 微信小程序（自定义 SSE 解析）

```javascript
// 微信小程序不支持 EventSource，需要手动处理 SSE 流
function parseSSE(responseText) {
  const events = [];
  const lines = responseText.split('\n');
  
  let currentEvent = {};
  for (const line of lines) {
    if (line.startsWith('event:')) {
      currentEvent.event = line.substring(7).trim();
    } else if (line.startsWith('data:')) {
      currentEvent.data = JSON.parse(line.substring(6).trim());
      events.push(currentEvent);
      currentEvent = {};
    }
  }
  
  return events;
}

// 使用示例
wx.request({
  url: analyzeUrl,
  method: 'POST',
  responseType: 'text',
  enableChunked: true, // 启用分块传输
  success: (res) => {
    const events = parseSSE(res.data);
    
    events.forEach(event => {
      switch(event.event) {
        case 'start':
          console.log('分析开始', event.data);
          break;
        case 'message':
          // 实时更新UI
          this.setData({
            analysisText: this.data.analysisText + event.data.message
          });
          break;
        case 'end':
          console.log('分析完成', event.data);
          break;
        case 'error':
          console.error('错误', event.data);
          break;
      }
    });
  }
});
```

---

## 4. 获取分析对话列表

### 请求

```
GET /ai/analyze/list/?analysis_type=personal&limit=20&offset=0
Authorization: Bearer <token>
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|-----|------|------|------|
| `analysis_type` | string | 否 | 筛选分析类型：`personal` 或 `company` |
| `model` | string | 否 | 筛选模型（通常不需要，因为分析模块固定使用 doubao） |
| `limit` | int | 否 | 每页数量，默认 50 |
| `offset` | int | 否 | 偏移量，默认 0 |

### 响应

```json
{
  "code": 0,
  "data": {
    "total": 125,
    "limit": 20,
    "offset": 0,
    "conversations": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": "user-uuid",
        "model": "doubao",
        "analysis_type": "personal",
        "title": "销售数据分析",
        "created_at": "2024-01-15 10:30:00",
        "updated_at": "2024-01-15 11:45:00",
        "message_count": 4
      }
    ]
  }
}
```

### 示例

```javascript
wx.request({
  url: 'http://api.example.com/ai/analyze/list/',
  method: 'GET',
  header: {
    'Authorization': `Bearer ${token}`
  },
  data: {
    analysis_type: 'personal',
    limit: 20,
    offset: 0
  },
  success: (res) => {
    if (res.data.code === 0) {
      const analyses = res.data.data.conversations;
      // 更新 UI
      this.setData({ analysisList: analyses });
    }
  }
});
```

---

## 5. 获取分析对话详情

### 请求

```
GET /ai/analyze/get/<conversation_id>/
Authorization: Bearer <token>
```

### 响应

```json
{
  "code": 0,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user-uuid",
    "model": "doubao",
    "analysis_type": "personal",
    "title": "销售数据分析",
    "messages": [
      {
        "role": "user",
        "content": "请对我上传的文件进行分析。"
      },
      {
        "role": "assistant",
        "content": "根据您上传的销售数据..."
      },
      {
        "role": "user",
        "content": "请给出改进建议"
      },
      {
        "role": "assistant",
        "content": "基于分析结果，建议..."
      }
    ],
    "files": [
      "chat-uploads/uuid/sales_data.xlsx"
    ],
    "created_at": "2024-01-15 10:30:00",
    "updated_at": "2024-01-15 11:45:00"
  }
}
```

### 示例

```javascript
wx.request({
  url: `http://api.example.com/ai/analyze/get/${conversationId}/`,
  method: 'GET',
  header: {
    'Authorization': `Bearer ${token}`
  },
  success: (res) => {
    if (res.data.code === 0) {
      const analysis = res.data.data;
      // 渲染对话历史
      this.setData({ 
        messages: analysis.messages,
        files: analysis.files
      });
    }
  }
});
```

---

## 6. 删除分析对话

### 请求

```
DELETE /ai/analyze/delete/<conversation_id>/
Authorization: Bearer <token>
```

### 响应

```json
{
  "code": 0,
  "message": "对话已删除"
}
```

### 示例

```javascript
wx.showModal({
  title: '确认删除',
  content: '确定要删除这个分析对话吗？',
  success: (res) => {
    if (res.confirm) {
      wx.request({
        url: `http://api.example.com/ai/analyze/delete/${conversationId}/`,
        method: 'DELETE',
        header: {
          'Authorization': `Bearer ${token}`
        },
        success: (res) => {
          if (res.data.code === 0) {
            wx.showToast({ title: '已删除', icon: 'success' });
            // 刷新列表
            this.loadAnalysisList();
          }
        }
      });
    }
  }
});
```

---

## 7. 获取用户配额

### 请求

```
GET /ai/analyze/quota/
Authorization: Bearer <token>
```

### 响应

```json
{
  "code": 0,
  "data": {
    "current_quota": 150,
    "personal_cost": 1,
    "company_cost": 2,
    "can_do_personal": true,
    "can_do_company": true
  }
}
```

### 示例

```javascript
wx.request({
  url: 'http://api.example.com/ai/analyze/quota/',
  method: 'GET',
  header: {
    'Authorization': `Bearer ${token}`
  },
  success: (res) => {
    if (res.data.code === 0) {
      const quota = res.data.data;
      this.setData({
        currentQuota: quota.current_quota,
        canAnalyze: quota.can_do_personal || quota.can_do_company
      });
      
      // 提示用户
      if (!quota.can_do_personal && !quota.can_do_company) {
        wx.showModal({
          title: '配额不足',
          content: '您的 AI 点数不足，请充值后继续使用',
          confirmText: '去充值',
          success: (res) => {
            if (res.confirm) {
              // 跳转到充值页面
              wx.navigateTo({ url: '/pages/recharge/recharge' });
            }
          }
        });
      }
    }
  }
});
```

---

## 错误码参考

| 错误码 | 说明 | 处理建议 |
|--------|------|---------|
| 0 | 成功 | - |
| 400 | 参数错误 | 检查请求参数是否完整且正确 |
| 402 | 配额不足 | 提示用户充值 |
| 404 | 对话不存在 | 检查 conversation_id 是否正确 |
| 500 | 服务器错误 | 稍后重试或联系技术支持 |

---

## 常见问题（FAQ）

### 1. 为什么首次分析必须上传文件？

数据分析的核心是基于数据进行分析。首次创建分析会话时，必须上传文件作为分析的基础数据源。后续的追问可以不上传新文件，直接基于已有文件进行讨论。

### 2. 可以同时上传多个文件吗？

可以。在创建分析或继续分析时，都支持上传多个文件。只需要在表单中添加多个 `files` 字段即可。

### 3. 分析使用的是什么模型？

数据分析模块固定使用**豆包（doubao）**模型，无需（也不能）指定其他模型。

### 4. 个人分析和企业分析有什么区别？

- **个人分析**：面向个人用户，提供简洁实用的分析建议，消耗 1 点/次
- **企业分析**：面向企业用户，提供更深入的战略性分析和行业洞察，消耗 2 点/次

两种模式使用的提示词不同，分析的深度和角度也有所差异。

### 5. 如何处理 SSE 流？

微信小程序不直接支持 EventSource，需要手动解析 SSE 格式的响应。参考上文的 `parseSSE` 函数示例。

### 6. 配额不足时会发生什么？

如果用户配额不足以进行分析，接口会返回 `code: 402` 错误，并说明所需配额和当前配额。前端应提示用户充值。

### 7. 分析对话可以删除吗？

可以。调用 `DELETE /ai/analyze/delete/<id>/` 接口即可删除对话。

### 8. 如何获取分析历史记录？

使用 `GET /ai/analyze/list/` 获取对话列表，然后使用 `GET /ai/analyze/get/<id>/` 获取具体对话的详细内容。

---

## 完整集成示例

参考 [ANALYZE_INTEGRATION.md](./ANALYZE_INTEGRATION.md) 获取完整的微信小程序集成代码示例。
