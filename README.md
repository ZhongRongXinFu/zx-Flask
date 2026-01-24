# 项目说明

本项目提供 AI 聊天、文件分析以及账号相关接口的 Flask 服务。本文档汇总接口文档链接、部署与使用方式，便于快速上手。

## 文档索引
- AI 接口文档：[docs/ai.md](docs/ai.md)
- 账号接口文档（如有）：[docs/account.md](docs/account.md)
- AI 相关说明与检查表（如适用）：[docs/ai.md](docs/ai.md)

## 快速开始
1) 准备环境
- 推荐 Python 3.10+。
- 安装依赖：`pip install -r requirements.txt`。

2) 配置环境变量
- 将必需的密钥写入环境变量或 `.env`（如有）：
  - `AI_DEEPSEEK_API_KEY`
  - 数据库等其他敏感配置，参考 `settings.py`。

3) 运行服务
- 开发模式直接启动：`python index.py`
- 默认监听 `localhost:8000`（如有变更以代码为准）。

4) 运行验证脚本（可选）
- 执行测试/校验脚本，例如：`python test.py`，或项目内提供的 `verify_fix.sh`、`test_file_fix.py` 等根据需要运行。

## 使用提示
- 所有文件上传现采用公网 URL 方式，请同时提供 `file_urls` 与 `file_names`，详见 AI 文档。
- DeepSeek 模型仅接受纯文本：附件会被后端转成 `[图片] URL` / `[文件] URL` 描述；多模态请使用 `doubao`。
- 流式 SSE 响应的处理方式与事件名示例在 AI 文档中有详细说明。

## 目录速览
- 应用入口与路由：`index.py`、`pages/` 下各模块
- AI 能力实现：`utils/ai/`
- 配置：`settings.py`
- 静态与上传：`static/`、`uploads/`、`temp/`
- SQL 脚本：`sql/`
- 文档：`docs/` 及根目录 `*.md`

如需更多细节或接口示例，请参阅对应文档链接。