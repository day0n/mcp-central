# ACE Music Gen Web Interface

ACE 音乐生成器的 Web 前端界面，提供可视化的多轮对话和音乐生成体验。

## 目录结构

```
web/
├── backend/                 # 后端桥接层
│   ├── api_server.py       # FastAPI 服务器
│   ├── state_tracker.py    # Agent 状态跟踪器
│   ├── models/            # API 数据模型
│   │   ├── __init__.py
│   │   ├── requests.py    # 请求模型
│   │   └── responses.py   # 响应模型
│   └── routes/            # API 路由
│       ├── __init__.py
│       ├── session.py     # 会话管理
│       ├── chat.py        # 对话接口
│       └── media.py       # 媒体文件
├── frontend/              # Next.js 前端
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── app/           # App Router 页面
│   │   ├── components/    # React 组件
│   │   ├── hooks/         # 自定义 Hooks
│   │   ├── lib/          # 工具函数
│   │   ├── stores/       # 状态管理 (Zustand)
│   │   └── types/        # TypeScript 类型定义
│   └── public/           # 静态资源
└── docker/               # Docker 配置 (后续)
    ├── Dockerfile.backend
    ├── Dockerfile.frontend
    └── docker-compose.yml
```

## 技术栈

### 后端 (Python)
- **FastAPI**: 高性能 API 框架
- **Pydantic**: 数据验证和序列化
- **asyncio**: 异步处理
- **Server-Sent Events**: 实时状态推送

### 前端 (TypeScript/React)
- **Next.js 14**: React 框架 (App Router)
- **TypeScript**: 类型安全
- **TailwindCSS**: 原子化 CSS
- **Radix UI**: 无头组件库
- **Zustand**: 轻量级状态管理
- **React Hook Form**: 表单处理

## 开发流程

1. **阶段 1**: 后端桥接层实现
2. **阶段 2**: 前端基础框架
3. **阶段 3**: 对话界面和状态可视化
4. **阶段 4**: 音乐播放和结果展示
5. **阶段 5**: 优化和部署

## 快速启动

### 开发环境
```bash
# 启动后端 (端口 8001)
cd web/backend
python api_server.py

# 启动前端 (端口 3000)
cd web/frontend
npm run dev
```

### 生产环境
```bash
# 构建和部署
make web-build
make web-deploy
```

## API 文档

详细的 API 接口文档请参考: [web_api_contract.md](../web_api_contract.md)