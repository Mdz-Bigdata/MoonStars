# MoonStars

一个功能强大的内容转换系统，支持将微信公众号、飞书、语雀文章一键转换为精美博客。

## ✨ 核心功能

- 🚀 **多平台支持**：支持微信公众号、飞书文档、语雀文档
- 📝 **智能解析**：自动提取文本、图片、表格等内容
- 🎨 **现代设计**：精美的玻璃态 UI 设计
- 📦 **批量转换**：支持批量导入多篇文章
- 💰 **专栏付费**：支持创建付费专栏（微信支付/支付宝）
- 📱 **响应式布局**：完美适配手机、平板、桌面

## 🛠️ 技术栈

### 后端
- **框架**：FastAPI + Python 3.14+
- **数据库**：SQLite (可切换 PostgreSQL)
- **ORM**：SQLAlchemy 2.0 (异步)
- **爬虫**：Requests + BeautifulSoup4

### 前端
- **框架**：React 18 + TypeScript
- **构建工具**：Vite
- **路由**：React Router
- **HTTP 客户端**：Axios
- **样式**：原生 CSS (现代设计系统)

## 📦 快速开始

### 环境要求

- Python 3.14+ (必须安装 Python 3.14)
- Node.js 18+ (推荐 20.x 或以上)
- SQLite (内置) 或 PostgreSQL 13+ (可选)
- **FFmpeg**: 必须安装并配置到系统环境变量（用于音视频处理和切片）
  - **macOS**: `brew install ffmpeg`
  - **Ubuntu/Debian**: `sudo apt install ffmpeg`
  - **Windows**: 推荐使用 `scoop install ffmpeg` 或下载对应二进制文件配置到 PATH

### 1. 后端启动

```bash
# 进入后端目录
cd backend

# 创建虚拟环境 (指定使用 Python 3.14)
python3.14 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 更新 pip 和构建工具 (指定官方源以防镜像源报错)
pip install -i https://pypi.org/simple --upgrade pip setuptools wheel

# 安装核心依赖
pip install -i https://pypi.org/simple -r requirements.txt

# 安装 Playwright 浏览器依赖 (用于页面渲染)
playwright install --with-deps

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件（默认配置已可用，使用 SQLite）

# 启动服务
python3.14 -m uvicorn app.main:app --reload --port 8000
```

后端服务将运行在 `http://localhost:8000`

API 文档地址：`http://localhost:8000/docs`

**默认管理员账户**：
- 用户名/邮箱：`admin`
- 密码：`admin123`
- 权限：管理员

> 💡 **提示**：首次启动时，如果数据库中没有 admin 账户，可以运行 `python create_admin.py` 创建默认管理员账户。

### 2. 前端启动

```bash
# 进入前端目录
cd frontend

# 推荐使用 Node.js 18+ 或 20.x
# 安装依赖
npm install --legacy-peer-deps

# 启动开发服务器
npm run dev
```

前端应用将运行在 `http://localhost:5173`

## 📚 使用指南

### 转换文章

1. 打开首页 `http://localhost:5173`
2. 在顶部输入框粘贴文章 URL（支持微信公众号、飞书、语雀）
3. 点击"立即转换"按钮
4. 等待抓取和解析完成
5. 转换完成后会自动显示在文章列表中

### 批量转换

1. 点击"批量转换"标签页
2. 每行粘贴一个文章 URL
3. 点击"开始批量转换"
4. 查看转换结果统计

### 查看文章

- 点击文章卡片进入详情页
- 支持文本、图片、表格、列表、代码等多种内容展示
- 美观的排版设计
- 底部可查看原文链接

### 创建专栏

```bash
# 使用 API 文档创建专栏
# 访问 http://localhost:8000/docs
# 找到 POST /api/columns 接口
# 填写专栏信息并提交
```

## 🎨 设计特色

- **玻璃态效果**：毛玻璃卡片设计，backdrop-filter 模糊效果
- **渐变色彩**：现代紫-粉渐变配色主题
- **流畅动画**：Hover 效果和过渡动画
- **响应式设计**：完美适配手机、平板、桌面设备
- **暗色主题**：深色背景 + 高对比度文本

## 🔧 配置说明

### 数据库配置

**默认使用 SQLite** (无需额外安装)：
```bash
DATABASE_URL=sqlite+aiosqlite:///./blog_converter.db
```

**切换到 PostgreSQL**：
1. 安装 PostgreSQL 驱动：`pip install asyncpg`
2. 修改 `.env` 文件：
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/blog_converter
   ```

### CORS 配置

在 `.env` 中配置允许的前端地址（逗号分隔）：
```
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### 支付配置（可选）

如需启用真实支付功能，需配置微信支付和支付宝商户信息：

```bash
# 微信支付
WECHAT_APP_ID=你的AppID
WECHAT_MCH_ID=你的商户号
WECHAT_API_KEY=你的API密钥

# 支付宝
ALIPAY_APP_ID=你的AppID
ALIPAY_PRIVATE_KEY_PATH=私钥路径
ALIPAY_PUBLIC_KEY_PATH=公钥路径
```

**注意**：没有配置支付密钥时，支付功能会使用模拟实现，返回示例二维码 URL。

## 📁 项目结构

```
resume-builder/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── main.py         # FastAPI 应用入口
│   │   ├── api/
│   │   │   └── endpoints.py    # API 路由定义
│   │   ├── core/
│   │   │   ├── config.py       # 配置管理
│   │   │   └── database.py     # 数据库连接
│   │   ├── models/         # SQLAlchemy ORM 模型
│   │   │   ├── article.py
│   │   │   ├── column.py
│   │   │   └── order.py
│   │   ├── schemas/        # Pydantic Schema
│   │   │   ├── article.py
│   │   │   ├── column.py
│   │   │   └── payment.py
│   │   ├── repository/     # 数据访问层
│   │   │   ├── article.py
│   │   │   ├── column.py
│   │   │   └── order.py
│   │   └── services/       # 业务逻辑层
│   │       ├── crawler.py      # 内容抓取
│   │       ├── parser.py       # 内容解析
│   │       ├── article.py      # 文章服务
│   │       └── payment.py      # 支付服务
│   ├── uploads/            # 图片上传目录
│   ├── requirements.txt    # Python 依赖
│   └── .env               # 环境变量配置
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── App.tsx        # 应用入口
│   │   ├── components/    # React 组件
│   │   │   ├── article-card.tsx
│   │   │   └── url-converter.tsx
│   │   ├── pages/         # 页面组件
│   │   │   ├── home.tsx
│   │   │   └── article-detail.tsx
│   │   ├── services/
│   │   │   └── api.ts         # API 服务封装
│   │   ├── types/
│   │   │   └── index.ts       # TypeScript 类型
│   │   └── styles/
│   │       └── index.css      # 设计系统
│   └── package.json
└── README.md              # 项目文档
```

## 🚀 API 接口

### 文章接口

- `POST /api/articles/convert` - 单篇文章转换
  - 请求体：`{ "url": "...", "column_id": "..." }`
  - 返回：文章对象
- `POST /api/articles/batch-convert` - 批量文章转换
  - 请求体：`{ "urls": [...], "column_id": "..." }`
  - 返回：转换结果统计
- `GET /api/articles` - 获取文章列表（支持分页、筛选）
  - Query 参数：`page`, `size`, `column_id`, `platform`
- `GET /api/articles/{id}` - 获取文章详情

### 专栏接口

- `POST /api/columns` - 创建专栏
- `GET /api/columns` - 获取所有专栏
- `GET /api/columns/{id}` - 获取专栏详情
- `GET /api/columns/{id}/articles` - 获取专栏的文章列表

### 支付接口

- `POST /api/orders/create` - 创建订单
  - 请求体：`{ "column_id": "...", "payment_method": "wechat/alipay" }`
  - 返回：订单信息 + 支付二维码
- `GET /api/orders/{id}/status` - 查询订单状态

### 健康检查

- `GET /api/health` - 服务健康检查

**完整 API 文档**：`http://localhost:8000/docs` (Swagger UI)

## 🐛 常见问题

### 1. 抓取失败怎么办？

- **确保 URL 格式正确**：复制完整的文章链接
- **平台反爬限制**：部分平台可能有反爬机制，建议使用公开文章
- **网络问题**：检查网络连接，某些平台可能需要代理
- **解决方案**：
  - 公众号：使用已分享的文章链接
  - 飞书/语雀：确保文档为公开状态

### 2. 图片加载失败？

- 确保后端 `uploads/` 目录有写入权限
- 检查原图片地址是否可访问
- 某些平台的图片有防盗链，可能无法下载

### 3. 数据库连接失败？

**使用 SQLite（默认）**：
- 无需额外配置，自动创建数据库文件

**使用 PostgreSQL**：
- 确认 PostgreSQL 服务正在运行
- 检查 `.env` 中的数据库配置
- 确保数据库用户有创建表的权限
- 安装 `asyncpg`：`pip install asyncpg`

### 4. 端口被占用？

```bash
# 查找占用端口的进程
lsof -ti:8000  # 后端
lsof -ti:5173  # 前端

# 终止进程
kill -9 <PID>
```

### 5. 虚拟环境问题？

**重要**：必须先激活虚拟环境再运行命令！

```bash
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

# 验证虚拟环境
which python  # 应该显示 venv 中的 Python 路径
```

## 📝 开发计划

### 短期优化
- [ ] 异步任务队列（Celery）处理批量转换
- [ ] Redis 缓存文章列表
- [ ] 图片 CDN 加速
- [ ] 更友好的错误提示

### 功能扩展
- [ ] 用户系统（注册/登录/个人中心）
- [ ] 文章在线编辑
- [ ] 评论系统
- [ ] 全文搜索（Elasticsearch）
- [ ] 数据统计和图表
- [ ] SEO 优化（meta 标签、sitemap）

### 专栏和支付
- [ ] 真实支付集成（配置商户）
- [ ] 用户购买记录和权限验证
- [ ] 专栏详情页面
- [ ] 支付弹窗组件完善

## 🧪 测试

```bash
# 后端测试
cd backend
pytest tests/ -v

# 前端测试
cd frontend
npm run test
```

## 📄 许可证

MIT License

## 👨‍💻 开发团队

由 Antigravity AI 开发

---

## 🆘 获取帮助

- **查看 API 文档**：http://localhost:8000/docs
- **查看项目 Walkthrough**：查看 `walkthrough.md` 了解实现细节
- **报告问题**：在项目中创建 Issue

## 🎯 快速命令参考

```bash
# 后端
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev
```

**祝您使用愉快！** 🎉
