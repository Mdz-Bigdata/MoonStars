# MoonStars - 配置与部署文档

## 功能概览

本工具支持从网页URL生成精美PPT，集成了以下核心能力：

| 能力 | 说明 | 依赖 |
|------|------|------|
| **python-pptx** | 结构化PPT生成（10+主题） | 内置 |
| **Mermaid.js** | 流程图/思维导图/架构图 | 远程API / 本地CLI |
| **ComfyUI + Stable Diffusion** | AI图片生成 | ComfyUI服务 |
| **banana-slides** | AI全图式幻灯片生成 | Gemini API |
| **Unsplash / Pexels** | 图库配图搜索 | API Key（免费） |

### 三种生成模式

- **标准模式 (standard)**：结构化PPT + Mermaid图表 + 智能配图，开箱即用
- **AI视觉模式 (ai_visual)**：banana-slides全图式PPT，效果最精美（需配置Gemini）
- **混合模式 (hybrid)**：AI背景 + 结构化文字叠加，兼顾美观和可编辑性

---

## 环境要求

- **Python** ≥ 3.10
- **Node.js** ≥ 16
- **PostgreSQL**（项目数据库）
- **ComfyUI**（可选，用于SD生图）
- **mermaid-cli**（可选，用于本地Mermaid渲染）

---

## 快速开始（标准模式）

标准模式无需额外服务，直接启动即可使用。

### 1. 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器（网页爬取需要）
playwright install chromium

# 启动后端
uvicorn app.main:app --reload --port 8483
```

### 2. 前端启动

```bash
cd frontend
npm install
npm run dev
```

### 3. 访问

打开 `http://localhost:5173`，导航到"URL转PPT"页面。

---

## 环境变量配置

编辑 `backend/.env` 文件：

### 核心AI配置（必须）

```bash
# DeepSeek（大纲生成，必须配置）
AI_BASE_URL=https://api.deepseek.com
AI_DEFAULT_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your_deepseek_api_key
```

### ComfyUI / Stable Diffusion（可选）

```bash
ENABLE_SD=true                          # 开启AI生图
COMFYUI_URL=http://127.0.0.1:8188      # ComfyUI 地址
SD_MODEL_NAME=sd_xl_base_1.0.safetensors  # 模型名
SD_STEPS=20                              # 采样步数
SD_CFG=7.0                               # CFG Scale
```

### banana-slides AI PPT（可选）

```bash
BANANA_SLIDES_ENABLED=true               # 启用AI视觉模式
BANANA_SLIDES_AI_PROVIDER=gemini         # gemini / openai
GOOGLE_API_KEY=your_gemini_api_key       # Gemini API Key
```

### Mermaid（可选）

```bash
MERMAID_CLI_PATH=/usr/local/bin/mmdc     # 本地CLI路径（留空用远程API）
```

### 图库API（可选）

```bash
UNSPLASH_ACCESS_KEY=your_key             # https://unsplash.com/developers
PEXELS_API_KEY=your_key                  # https://www.pexels.com/api/
```

---

## ComfyUI 安装与配置

### 安装 ComfyUI

```bash
# 克隆 ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 安装依赖
pip install -r requirements.txt

# 下载 SDXL 模型（推荐）
# 将模型文件放到 ComfyUI/models/checkpoints/ 目录
# 推荐下载：sd_xl_base_1.0.safetensors
```

### 启动 ComfyUI（API模式）

```bash
python main.py --listen 0.0.0.0 --port 8188
```

### 验证连接

```bash
curl http://127.0.0.1:8188/system_stats
# 应返回系统信息 JSON
```

---

## banana-slides 配置

banana-slides-lib 已包含在项目的 `banana-slides-lib/` 目录中。

### 获取 Gemini API Key

1. 访问 https://ai.google.dev/
2. 点击 "Get an API key"
3. 将获取的 Key 填入 `.env` 的 `GOOGLE_API_KEY`

### 启用 banana-slides

在 `.env` 中设置：
```bash
BANANA_SLIDES_ENABLED=true
GOOGLE_API_KEY=your_gemini_api_key
```

---

## Mermaid.js 本地渲染（可选）

```bash
npm install -g @mermaid-js/mermaid-cli

# 验证安装
mmdc --version

# 配置路径
# .env 中设置 MERMAID_CLI_PATH 为 mmdc 路径
# 或留空，系统会自动使用 mermaid.ink 远程API
```

---

## Docker 部署

```bash
# 启动所有服务
docker-compose up -d

# 仅启动后端
docker-compose up -d backend

# 查看日志
docker-compose logs -f backend
```

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| PPT生成失败 | 检查 `DEEPSEEK_API_KEY` 是否有效 |
| ComfyUI连接失败 | 确认 ComfyUI 已启动且 URL 正确 |
| 图片不生成 | 检查 `ENABLE_SD=true` 且模型文件存在 |
| banana-slides不可用 | 检查 `BANANA_SLIDES_ENABLED=true` 和 `GOOGLE_API_KEY` |
| Mermaid图表空白 | 检查网络（远程API需要访问 mermaid.ink） |
| 网页爬取失败 | 执行 `playwright install chromium` |
| 前端编译错误 | 执行 `npm install` 更新依赖 |

### 查看服务状态

```bash
# 检查引擎状态
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8483/api/ppt/engines
```
