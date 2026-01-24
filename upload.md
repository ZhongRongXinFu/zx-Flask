# 文件上传接口文档

## 概述

统一的文件上传服务，支持单个文件上传、批量上传，提供灵活的文件分类和自定义文件名功能。所有上传文件将保存到本地存储，并返回访问 URL。

---

## 基础信息

- **基础 URL**: `https://api.zhongrongxinfu.cn`
- **认证方式**: 需要登录（JWT Token）
- **内容类型**: `multipart/form-data`

---

## API 端点

### 1. 单个文件上传

#### 请求

```
POST /upload/
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

#### 请求参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `file` | File | 是 | 要上传的文件 |
| `category` | String | 否 | 文件分类，用于组织存储目录。默认值: `uploads` |
| `subcategory` | String | 否 | 二级分类，用于在 category 下创建子目录 |
| `subsubcategory` | String | 否 | 三级分类，用于在 subcategory 下再创建子目录 |
| `filename` | String | 否 | 自定义文件名（不含扩展名），扩展名将使用原始文件的扩展名。如果不提供则自动生成 UUID |

#### 请求示例

**示例 1：自动生成文件名**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -H "Authorization: Bearer your_token" \
  -F "file=@photo.jpg" \
  -F "category=product"
```

**示例 2：指定自定义文件名**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -H "Authorization: Bearer your_token" \
  -F "file=@photo.jpg" \
  -F "category=product" \
  -F "filename=my-product-image"
```


**示例 3：使用二级目录**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -H "Authorization: Bearer your_token" \
  -F "file=@photo.jpg" \
  -F "category=product" \
  -F "subcategory=electronics" \
  -F "filename=item-001"
```

上述示例中，文件将被保存到 `product/electronics/item-001.jpg`

**示例 4：使用三级目录**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -H "Authorization: Bearer your_token" \
  -F "file=@photo.jpg" \
  -F "category=product" \
  -F "subcategory=electronics" \
  -F "subsubcategory=mobile" \
  -F "filename=item-002"
```

上述示例中，文件将被保存到 `product/electronics/mobile/item-002.jpg`

#### 成功响应（200）

```json
{
  "code": 200,
  "message": "上传成功",
  "data": {
    "filename": "photo.jpg",
    "url": "https://static.zhongrongxinfu.cn/product/a1b2c3d4e5f6.jpg",
    "path": "/product/a1b2c3d4e5f6.jpg",
    "size": 245678,
    "type": "image",
    "uploaded_at": "2026-01-19T10:30:00.123456"
  }
}
```

**示例：ai-chat 类别自动转换 Office 文件的响应**

```json
{
  "code": 200,
  "message": "上传成功，文件已转换为 PDF",
  "data": {
    "filename": "document.docx",
    "url": "https://static.zhongrongxinfu.cn/ai-chat/document.pdf",
    "path": "/ai-chat/document.pdf",
    "size": 156789,
    "type": "document",
    "converted": true,
    "original_filename": "document.docx",
    "uploaded_at": "2026-01-19T10:30:00.123456"
  }
}
```

**说明**：
- `converted`: 表示是否进行了自动转换（Office→PDF）
- `original_filename`: 原始上传的文件名（当发生转换时包含此字段）
- 转换后的文件类型始终为 PDF，扩展名为 `.pdf`

#### 错误响应

**缺少文件（400）**

```json
{
  "code": 400,
  "message": "请选择要上传的文件"
}
```

**不支持的文件类型（400）**

```json
{
  "code": 400,
  "message": "不支持的文件类型: .exe"
}
```

**文件过大（400）**

```json
{
  "code": 400,
  "message": "文件大小超过限制（最大 100MB）"
}
```

---

### 2. 批量文件上传

#### 请求

```
POST /upload/batch/
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

#### 请求参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `files` | File[] | 是 | 多个文件 |
| `category` | String | 否 | 文件分类。默认值: `uploads` |
| `subcategory` | String | 否 | 二级分类，用于在 category 下创建子目录 |
| `subsubcategory` | String | 否 | 三级分类，用于在 subcategory 下再创建子目录 |
| `filenames` | String (JSON) | 否 | 对应文件的自定义文件名（不含扩展名），支持数组或对象格式 |

#### 文件名格式

**数组格式**（按文件顺序对应）：

```
filenames=["file1.jpg", "file2.png", "file3.jpg"]
```

**对象格式**（按索引对应）：

```
filenames={"0": "file1.jpg", "1": "file2.png", "2": "file3.jpg"}
```

#### 请求示例

**示例 1：自动生成所有文件名**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/batch/ \
  -H "Authorization: Bearer your_token" \
  -F "files=@image1.jpg" \
  -F "files=@image2.png" \
  -F "files=@image3.jpg" \
  -F "category=product"
```

**示例 2：指定自定义文件名（数组格式）**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/batch/ \
  -H "Authorization: Bearer your_token" \
  -F "files=@image1.jpg" \
  -F "files=@image2.png" \
  -F "files=@image3.jpg" \
  -F "category=product" \
  -F 'filenames=["product-main", "product-detail1", "product-detail2"]'
```

**示例 3：指定自定义文件名（对象格式）**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/batch/ \
  -H "Authorization: Bearer your_token" \
  -F "files=@image1.jpg" \
  -F "files=@image2.png" \
  -F "category=product" \
  -F 'filenames={"0": "product-main", "1": "product-detail"}'
```


**示例 4：使用二级目录（数组格式）**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/batch/ \
  -H "Authorization: Bearer your_token" \
  -F "files=@image1.jpg" \
  -F "files=@image2.png" \
  -F "files=@image3.jpg" \
  -F "category=product" \
  -F "subcategory=electronics" \
  -F 'filenames=["item1", "item2", "item3"]'
```

上述示例中，文件将被保存到 `product/electronics/` 下

**示例 5：使用三级目录（数组格式）**

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/batch/ \
  -H "Authorization: Bearer your_token" \
  -F "files=@image1.jpg" \
  -F "files=@image2.png" \
  -F "files=@image3.jpg" \
  -F "category=product" \
  -F "subcategory=electronics" \
  -F "subsubcategory=mobile" \
  -F 'filenames=["item1", "item2", "item3"]'
```

上述示例中，文件将被保存到 `product/electronics/mobile/` 下

#### 成功响应（200）

```json
{
  "code": 200,
  "message": "批量上传完成，成功 3 个，失败 0 个",
  "data": {
    "success": [
      {
        "filename": "image1.jpg",
        "url": "https://static.zhongrongxinfu.cn/product/product-main.jpg",
        "path": "/product/product-main.jpg",
        "size": 245678,
        "type": "image",
        "uploaded_at": "2026-01-19T10:30:00.123456"
      },
      {
        "filename": "image2.png",
        "url": "https://static.zhongrongxinfu.cn/product/product-detail1.png",
        "path": "/product/product-detail1.png",
        "size": 156234,
        "type": "image",
        "uploaded_at": "2026-01-19T10:30:01.234567"
      },
      {
        "filename": "image3.jpg",
        "url": "https://static.zhongrongxinfu.cn/product/product-detail2.jpg",
        "path": "/product/product-detail2.jpg",
        "size": 312456,
        "type": "image",
        "uploaded_at": "2026-01-19T10:30:02.345678"
      }
    ],
    "failed": []
  }
}
```

#### 部分失败响应（200，包含失败项）

```json
{
  "code": 200,
  "message": "批量上传完成，成功 2 个，失败 1 个",
  "data": {
    "success": [
      {
        "filename": "image1.jpg",
        "url": "https://static.zhongrongxinfu.cn/product/product-main.jpg",
        "path": "/product/product-main.jpg",
        "size": 245678,
        "type": "image",
        "uploaded_at": "2026-01-19T10:30:00.123456"
      },
      {
        "filename": "image2.png",
        "url": "https://static.zhongrongxinfu.cn/product/product-detail1.png",
        "path": "/product/product-detail1.png",
        "size": 156234,
        "type": "image",
        "uploaded_at": "2026-01-19T10:30:01.234567"
      }
    ],
    "failed": [
      {
        "filename": "document.exe",
        "error": "不支持的文件类型: .exe"
      }
    ]
  }
}
```

---

### 3. 获取上传配置

#### 请求

```
GET /upload/config/
```

**说明**：此接口不需要身份认证

#### 成功响应（200）

```json
{
  "code": 200,
  "message": "获取配置成功",
  "data": {
    "allowed_extensions": {
      "image": ["png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "ico"],
      "document": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"],
      "other": ["zip", "rar", "7z", "tar", "gz"]
    },
    "max_file_size": 104857600,
    "max_file_size_mb": 100,
    "base_url": "https://static.zhongrongxinfu.cn"
  }
}
```

---

## 支持的文件类型

### 图片（Image）
- `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.svg`, `.ico`

### Office 文档（当 category=ai-chat 时自动转换为 PDF）
- `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`
  - **自动转换说明**：当上传到 `ai-chat` 类别时，这些文件会自动转换为 PDF 格式
  - **转换时间**：通常需要 1-10 秒，具体时间取决于文件大小和复杂度
  - **响应包含转换状态**：返回结果中会包含 `converted: true/false` 字段表示是否已转换

### 文档（Document）
- `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.txt`, `.md`, `.csv`
  - **注意**：Word、Excel、PowerPoint 文件仅在 `category=ai-chat` 时可上传（自动转换为 PDF）
  - 其他类别上传这些格式会返回文件类型不支持错误

### 其他（Other）
- `.zip`, `.rar`, `.7z`, `.tar`, `.gz`

---

## 限制条件

| 项目 | 限制 |
|------|------|
| 最大文件大小 | 100 MB |
| 单次批量上传最大文件数 | 无限制 |
| 认证要求 | 需要登录（大部分接口） |
| 文件编码 | 任意 |

---

## 文件存储结构

上传的文件按照以下结构组织存储：

```
uploads/
├── product/
│   ├── a1b2c3d4e5f6.jpg
│   ├── b2c3d4e5f6a1.png
│   ├── product-main.jpg
│   └── electronics/                    # 二级目录
│       ├── item-001.jpg
│       └── item-002.jpg
├── avatar/
│   ├── user-123.jpg
│   └── user-456.png
└── document/
    ├── invoice-001.pdf
    └── contract-001.docx
```

---

## 响应格式

所有 API 响应遵循统一格式：

```json
{
  "code": 200,           // HTTP 状态码
  "message": "操作结果信息",
  "data": {}            // 返回的数据（错误时可能为空）
}
```

### 状态码说明

| 状态码 | 说明 |
|------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误或文件验证失败 |
| 401 | 未认证或认证失败 |
| 500 | 服务器错误 |

---

## 最佳实践

### 1. 总是指定 category

为了便于文件管理，建议在上传时指定合理的 `category`：

```bash
# 产品图片
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -F "file=@product.jpg" \
  -F "category=product"

# 用户头像
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -F "file=@avatar.jpg" \
  -F "category=avatar"

# 文档
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -F "file=@invoice.pdf" \
  -F "category=document"
```

### 2. 使用二级目录组织文件

二级目录特別有用于需要整理大量文件的场景：

```bash
# 为商品类目组织不同的子类型
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -F "file=@product.jpg" \
  -F "category=product" \
  -F "subcategory=electronics"

# 为每个用户上传的文件并按类型子分类
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -F "file=@avatar.jpg" \
  -F "category=avatar" \
  -F "subcategory=user-12345"
```

### 3. 对于重要数据，使用自定义 filename

如果需要确保文件路径的一致性（比如商品的主图），使用 `filename` 指定固定的文件名（不含扩展名，扩展名会自动使用原始文件的扩展名）：

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -F "file=@product.jpg" \
  -F "category=product" \
  -F "filename=product-12345-main"
```

上述示例中，上传的是 JPG 文件，提供的 `filename` 是 `product-12345-main`，最终保存的文件名会是 `product-12345-main.jpg`。

这样后续更新该商品的主图时，使用相同的 `filename` 即可覆盖之前的文件。

### 4. 处理批量上传的部分失败

批量上传时，即使部分文件失败也会返回 200 状态码。需要检查响应中的 `success` 和 `failed` 数组来判断每个文件的上传情况：

```javascript
// 伪代码
const response = await uploadBatch(files);
if (response.data.failed.length > 0) {
  console.error('以下文件上传失败：', response.data.failed);
}
```

### 5. 使用返回的 URL

上传成功后，使用返回的 `url` 字段作为文件的访问地址：

```javascript
// 响应示例
{
  "url": "https://static.zhongrongxinfu.cn/product/a1b2c3d4e5f6.jpg"
}

// 在需要保存文件引用时，保存这个 URL
productData.image = "https://static.zhongrongxinfu.cn/product/a1b2c3d4e5f6.jpg"
```

### 6. 上传 Office 文件到 ai-chat 类别（自动转换为 PDF）

当上传 Word、Excel 或 PowerPoint 文件到 `ai-chat` 类别时，系统会自动将其转换为 PDF 格式：

```bash
# 上传 Word 文档到 ai-chat 类别，系统会自动转换为 PDF
curl -X POST https://api.zhongrongxinfu.cn/upload/ \
  -H "Authorization: Bearer your_token" \
  -F "file=@contract.docx" \
  -F "category=ai-chat" \
  -F "filename=contract-001"
```

响应示例：

```json
{
  "code": 200,
  "message": "上传成功，文件已转换为 PDF",
  "data": {
    "filename": "contract-001.pdf",
    "url": "https://static.zhongrongxinfu.cn/ai-chat/contract-001.pdf",
    "path": "/ai-chat/contract-001.pdf",
    "size": 245678,
    "type": "document",
    "converted": true,
    "original_filename": "contract.docx",
    "uploaded_at": "2026-01-19T10:30:00.123456"
  }
}
```

**说明**：
- 支持转换的格式：`.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`
- 转换过程自动进行，无需额外参数
- 转换后的文件会被保存为 PDF 格式
- 响应中的 `converted: true` 表示文件已转换
- 转换通常需要 1-10 秒，具体时间取决于文件大小

### 7. 批量上传 Office 文件到 ai-chat 类别

```bash
curl -X POST https://api.zhongrongxinfu.cn/upload/batch/ \
  -H "Authorization: Bearer your_token" \
  -F "files=@document1.docx" \
  -F "files=@spreadsheet.xlsx" \
  -F "files=@presentation.pptx" \
  -F "category=ai-chat" \
  -F 'filenames=["doc1", "sheet1", "slide1"]'
```

响应示例：

```json
{
  "code": 200,
  "message": "批量上传完成，成功 3 个，失败 0 个",
  "data": {
    "success": [
      {
        "filename": "doc1.pdf",
        "url": "https://static.zhongrongxinfu.cn/ai-chat/doc1.pdf",
        "path": "/ai-chat/doc1.pdf",
        "size": 156789,
        "type": "document",
        "converted": true,
        "original_filename": "document1.docx",
        "uploaded_at": "2026-01-19T10:30:00.123456"
      },
      {
        "filename": "sheet1.pdf",
        "url": "https://static.zhongrongxinfu.cn/ai-chat/sheet1.pdf",
        "path": "/ai-chat/sheet1.pdf",
        "size": 234567,
        "type": "document",
        "converted": true,
        "original_filename": "spreadsheet.xlsx",
        "uploaded_at": "2026-01-19T10:30:02.234567"
      },
      {
        "filename": "slide1.pdf",
        "url": "https://static.zhongrongxinfu.cn/ai-chat/slide1.pdf",
        "path": "/ai-chat/slide1.pdf",
        "size": 312456,
        "type": "document",
        "converted": true,
        "original_filename": "presentation.pptx",
        "uploaded_at": "2026-01-19T10:30:04.312456"
      }
    ],
    "failed": []
  }
}
```

所有文件都自动转换为 PDF，`converted: true` 表示转换成功。
---

## 错误处理示例

### Python（使用 requests）

```python
import requests
import json

# 单个文件上传
files = {'file': open('photo.jpg', 'rb')}
data = {'category': 'product'}
headers = {'Authorization': f'Bearer {token}'}

response = requests.post(
    'https://api.zhongrongxinfu.cn/upload/',
    files=files,
    data=data,
    headers=headers
)

if response.status_code == 200:
    result = response.json()
    if result['code'] == 200:
        print(f"上传成功: {result['data']['url']}")
    else:
        print(f"上传失败: {result['message']}")
else:
    print(f"请求失败: {response.status_code}")
```

### JavaScript（使用 fetch）

```javascript
// 单个文件上传
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('category', 'product');

const response = await fetch('https://api.zhongrongxinfu.cn/upload/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

const result = await response.json();
if (result.code === 200) {
  console.log('上传成功:', result.data.url);
} else {
  console.error('上传失败:', result.message);
}
```

### JavaScript（使用 axios）

```javascript
// 单个文件上传
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('category', 'product');

try {
  const response = await axios.post(
    'https://api.zhongrongxinfu.cn/upload/',
    formData,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      }
    }
  );
  
  if (response.data.code === 200) {
    console.log('上传成功:', response.data.data.url);
  } else {
    console.error('上传失败:', response.data.message);
  }
} catch (error) {
  console.error('请求失败:', error);
}
```

---

## 常见问题

### Q: 如何获取上传文件的公网访问 URL？

A: 上传成功后，响应中的 `url` 字段即为公网访问地址，格式为 `https://static.zhongrongxinfu.cn/{category}/{filename}`

### Q: 上传的文件可以被覆盖吗？

A: 可以。上传时指定相同的 `file_uuid` 可以覆盖之前的文件。例如，商品主图的更新可以使用固定的 UUID。

### Q: 如何删除已上传的文件？

A: 目前上传接口不提供删除功能，文件管理需要通过其他途径处理。

### Q: 支持什么图片格式？

A: 支持 `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.webp`, `.svg`, `.ico`

### Q: 最大能上传多大的文件？

A: 最大 100 MB

### Q: 批量上传时，如果某个文件失败，是否会影响其他文件？

A: 不会。批量上传采用独立处理方式，单个文件失败不会影响其他文件的上传。

### Q: 什么时候会发生 Office→PDF 自动转换？

A: 当上传文件的 `category` 参数值为 `ai-chat` 时，系统会自动检查文件类型。如果是 Office 格式（`.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`），会自动转换为 PDF。其他类别则不会进行转换。

### Q: Office 文件转换为 PDF 后，原始文件是否会被保留？

A: 不会。转换成功后，系统会删除原始的 Office 文件，只保留转换后的 PDF。响应中的 `original_filename` 字段记录了原始文件的名称以供参考。

### Q: Office→PDF 转换需要多长时间？

A: 通常需要 1-10 秒，具体取决于文件大小和复杂度。系统的最大等待时间为 300 秒，如果超过此时间，转换将失败并返回错误。

### Q: 如果 Office 文件转换失败了会怎样？

A: 如果转换失败，上传接口会返回 400 错误响应，包含详细的错误信息说明转换失败的原因。

### Q: 我可以上传 Word 文件到其他类别（非 ai-chat）吗？

A: 不可以。Word、Excel 和 PowerPoint 文件只有在 `category=ai-chat` 时才被接受。上传到其他类别会返回"不支持的文件类型"错误。
---

## 更新历史

| 版本 | 日期 | 更新内容 |
|------|------|--------|
| 1.0 | 2026-01-19 | 初版发布，包含单个上传、批量上传、配置查询功能 |
| 1.1 | 2026-01-20 | 添加 ai-chat 类别的 Office→PDF 自动转换功能，支持 Word、Excel、PowerPoint 文件上传和自动转换 |
