# 标注系统

轻量级图片标注工具，直接读写 JSONL 文件。

## 启动

### 开发模式（直连，无 Nginx）

```bash
cd version1
./start.sh
# 或手动:
python -m backend.main --host 0.0.0.0 --port 8000
python -m http.server 5173 --directory frontend
```

访问 `http://127.0.0.1:5173`

### 生产模式（Nginx 反向代理）

```bash
cd version1
./start.sh --prod
```

自动安装 Nginx、配置反向代理、绑定 `127.0.0.1`。访问 `http://服务器IP`。

## 管理命令

```bash
./stop_all.sh    # 停止所有服务
./status.sh      # 查看运行状态
```

## 使用流程

1. 自动扫描 `jsonl/` 目录下的所有 `.jsonl` 文件，显示为文件树
2. 点击数据集展开 checkpoint 列表
3. 点击 checkpoint 进入标注工作台
4. 左侧看图片（滚轮缩放、拖拽平移），右侧编辑 prompt 和 answer
5. 编辑 answer 后 1.5 秒自动保存，也可点"保存"或按 Ctrl+S
6. 键盘左右箭头切换记录

## 数据格式

```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "images": ["data/CP1-bedding/example.jpg"]
}
```

`images[0]` 的第一级路径作为 checkpoint 名称（如 `CP1-bedding`）。

## 目录

```
backend/
  main.py           启动入口
  server.py         HTTP 路由和请求处理
  datastore.py      JSONL 数据缓存
  db.py             用户数据库（SQLite）
  config.py         路径和端口配置
  image_server.py   图片服务（ETag、Range）
  record_utils.py   记录摘要和统计
  utils/datasets.py 数据解析工具
frontend/           前端页面（原生 HTML/JS/CSS）
data/               图片目录（按 checkpoint 分类）
jsonl/              JSONL 标注数据
```

## 初始账号

`admin` / `admin`（首次部署后请修改密码）
