# VLM-Labeling

轻量级图片标注系统，用于 VLM（Vision Language Model）数据质量检查标注。直接读写 JSONL 文件，无需数据库，零第三方依赖。

## 功能特性

- 图片标注工作台：左侧查看图片（滚轮缩放、拖拽平移），右侧编辑 System/User/Assistant Prompt
- 数据集管理：自动扫描 JSONL 目录，按 checkpoint 分组展示
- 数据分析：按数据集统计标注进度、通过率、标注分布
- 用户系统：注册需管理员审批，Token 认证
- 批量操作：支持批量替换 Prompt 内容
- 自动保存：编辑后 1.5 秒自动保存，支持 Ctrl+S 手动保存
- 图片加载：带进度条和速度显示，支持 ETag 缓存和 Range 请求
- 生产部署：一键启动脚本，自动配置 Nginx 反向代理

## 快速开始

### 环境要求

- Python 3.8+（仅使用标准库，无需 pip install）
- 无需 Node.js、无需数据库

### 启动

```bash
cd version1

# 开发模式（直连，无 Nginx）
./start.sh

# 或手动启动
python -m backend.main --host 0.0.0.0 --port 8000
python -m http.server 5173 --directory frontend
```

访问 `http://127.0.0.1:5173`，初始账号 `admin` / `admin`。

### 生产部署

```bash
cd version1
./start.sh --prod
```

自动安装 Nginx、配置反向代理、绑定 `127.0.0.1`。访问 `http://服务器IP`。

详细部署说明见 [部署文档](version1/部署文档.md)。

## 使用流程

1. 上传 JSONL 数据文件到 `jsonl/` 目录，图片放到 `data/` 目录
2. 登录系统，左侧文件树自动显示数据集
3. 点击数据集展开 checkpoint 列表
4. 点击 checkpoint 进入标注工作台
5. 左侧查看图片，右侧编辑 System/User/Assistant 内容
6. 键盘左右箭头切换记录，编辑后自动保存

## 数据格式

JSONL 文件，每行一个 JSON 对象：

```json
{
  "messages": [
    {"role": "system", "content": "你是一个图片质量检查助手..."},
    {"role": "user", "content": "请检查这张图片的质量..."},
    {"role": "assistant", "content": "1. 清晰度：通过\n2. 光线：通过\n\n判定：通过\n原因：图片质量良好"}
  ],
  "images": ["data/CP1-bedding/example.jpg"]
}
```

- `images[0]` 的第一级路径作为 checkpoint 名称（如 `CP1-bedding`）
- 图片按 checkpoint 子目录组织在 `data/` 下

## 技术架构

```
version1/
├── backend/                 # Python 后端（标准库）
│   ├── main.py              # 启动入口，参数解析
│   ├── server.py            # HTTP 路由和请求处理
│   ├── datastore.py         # JSONL 数据缓存（线程安全）
│   ├── db.py                # SQLite 用户管理
│   ├── config.py            # 路径和端口配置
│   ├── image_server.py      # 图片服务（ETag、Range）
│   ├── record_utils.py      # 记录摘要和统计
│   └── utils/datasets.py    # 数据解析工具
├── frontend/                # 前端（原生 HTML/JS/CSS）
│   ├── index.html           # 页面结构
│   ├── app.js               # 业务逻辑
│   └── styles.css           # 样式
├── start.sh                 # 启动脚本（支持 --prod）
├── stop_all.sh              # 停止脚本
├── status.sh                # 状态检查
├── nginx.conf               # Nginx 配置
└── label-system.service     # systemd 服务配置
```

### 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 标准库（http.server、sqlite3） |
| 前端 | 原生 HTML / CSS / JavaScript |
| 数据存储 | JSONL 文件 + SQLite（用户认证） |
| 部署 | Nginx + systemd |

### 设计决策

- **零依赖**：后端仅用 Python 标准库，前端无构建工具，降低部署门槛
- **文件即数据库**：JSONL 文件直接读写，便于版本控制和数据迁移
- **内存缓存**：DataStore 线程安全缓存，读写性能优异
- **Token 认证**：服务端内存存储，注册需管理员审批

## 管理命令

```bash
cd version1
./stop_all.sh    # 停止所有服务
./status.sh      # 查看运行状态
```

## 文档

- [部署文档](version1/部署文档.md) — 完整的服务器部署指南
- [问题排查](version1/问题排查与解决方案.md) — 常见问题和解决方案

## License

MIT
