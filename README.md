# Board Game List

这个仓库用 `data.json` 维护桌游列表，并用 `sync_bgg_collection.py` 从 BoardGameGeek 同步资料。

## 运行

首次运行先安装依赖：

```bash
npm install
```

根据 `data.json` 生成网页：

```bash
python3 generate_html.py
```

本地启动配置放在两个 Git 忽略的环境文件里：

- `.env.production.local`: production Docker 启动配置。
- `.env.development.local`: local development 启动配置。

两个文件都需要定义 `APP_HOST` 和 `APP_PORT`。

### Production in Docker

先创建本地 production 环境文件。这个文件会被 Git 忽略：

```bash
cat > .env.production.local <<'EOF'
APP_HOST=0.0.0.0
APP_PORT=<production-port>
EOF
```

然后用 Docker 构建并启动 production container：

```bash
./production-docker.sh
```

### Local Development

先创建本地 development 环境文件。这个文件会被 Git 忽略：

```bash
cat > .env.development.local <<'EOF'
APP_HOST=0.0.0.0
APP_PORT=<local-dev-port>
EOF
```

```bash
./development-server.sh
```

development 启动脚本会读取 `.env.development.local`，停止占用同一端口的旧进程，然后在后台运行 `npm run start`。具体监听地址和端口由本地环境文件提供。

## Package scripts

```bash
npm run start
```

- `npm run start`: 从仓库根目录启动静态文件服务器。需要通过环境变量提供 `APP_PORT`，可选提供 `APP_HOST`。

## Startup scripts

- `./production-docker.sh [start|stop|restart]`: 读取 `.env.production.local`，构建 Docker image，并替换同名 production container。
- `./development-server.sh [start|stop|restart]`: 读取 `.env.development.local`，停止占用 development 端口的旧进程，然后在后台运行 `npm run start`。

脚本日志写入 `.server-logs/`，该目录不会提交到 Git。

## 常用命令

从 BGG 同步数据：

```bash
python3 sync_bgg_collection.py
```

根据 `data.json` 生成网页：

```bash
python3 generate_html.py
```

## 数据结构

`data.json` 的顶层结构是：

```json
{
  "lastUpdated": "2026-05-23T03:23:00Z",
  "games": []
}
```

每个游戏使用 BGG 的游戏 ID 作为唯一标识。`alias` 是手动维护的中文别名，脚本同步时不会覆盖它。

## 私密配置

把 BGG 用户名、token、cookie 放到本地 `bgg_auth.json`。这个文件已经被 `.gitignore` 忽略，不会被 Git 跟踪。

先复制模板：

```bash
cp bgg_auth.example.json bgg_auth.json
```

然后编辑 `bgg_auth.json`：

```json
{
  "username": "your-bgg-username",
  "token": "your-bgg-application-token",
  "cookie": "",
  "tokenFile": "",
  "cookieFile": ""
}
```

字段说明：

- `username`: 你的 BGG 用户名。
- `token`: BGG application 的 Bearer token。
- `cookie`: 登录 BGG 后的 Cookie 字符串。只有同步 private collection 或不注册 application 只拉自己的 collection 时才需要。
- `tokenFile`: 如果不想把 token 直接写在 JSON 里，可以写一个 token 文件路径。
- `cookieFile`: 如果不想把 cookie 直接写在 JSON 里，可以写一个 cookie 文件路径。

命令行参数和环境变量会覆盖 `bgg_auth.json`。可用环境变量包括 `BGG_USERNAME`、`BGG_TOKEN`、`BGG_API_TOKEN`、`BGG_COOKIE`。

## 同步

完整同步：

```bash
python3 sync_bgg_collection.py
```

使用其它配置文件：

```bash
python3 sync_bgg_collection.py --auth-file /path/to/bgg_auth.json
```

同步前预览，不写入文件：

```bash
python3 sync_bgg_collection.py --dry-run
```

只同步某些 Collection 状态：

```bash
python3 sync_bgg_collection.py --collection-status owned --collection-status want-to-play
```

只更新 Collection 字段，不拉取 BGG 详情：

```bash
python3 sync_bgg_collection.py --skip-details
```

只按本地已有 ID 更新 BGG 详情，不读取 Collection：

```bash
python3 sync_bgg_collection.py --skip-collection
```

同步脚本只做两件事：

- 读取用户 Collection，按 BGG ID 新增或更新 `id`、`nameEn`、`year`、`userRating`、`status`。
- 按本地已有 ID 拉取 BGG 详情，更新 `weight`、`players`、`age`、`playingTime`、`bggRank`、`bggRating`。

标记规则：

- `collection: true` 表示游戏当前在 Collection 里。
- `collection: false` 表示游戏当前不在 Collection 里，或该条目的 `id` 是 `null`。
- `bgg: true` 表示本次按 ID 能从 BGG 找到该条目。
- `bgg: false` 表示本次按 ID 找不到，或该条目的 `id` 是 `null`。

脚本不会更新中文名、中文别名或本地机制分类。这些信息需要作为独立步骤人工或通过 Codex 从互联网上补全。

## AI/联网研究补全

`research_game_metadata.py` 是独立的研究补全步骤，用来补齐缺失的 `nameZh` 和 `mechanisms`。

```bash
python3 research_game_metadata.py
```

这个脚本会：

- 读取 `data.json`。
- 只补缺失的 `nameZh` 和 `mechanisms`，默认不覆盖已有值。
- 不修改 `alias`。
- 使用 BGG alternate names 和 mechanics 作为候选。
- 尝试读取公开网页文本辅助查证机制，再根据本地机制分类做映射。
- 对 BGG 或公开数据源不完整的条目，使用脚本里的内置研究表补充。

如果需要重新覆盖已有中文名和机制：

```bash
python3 research_game_metadata.py --overwrite
```

如果只想使用 BGG XML 和脚本内置研究表，不访问额外网页：

```bash
python3 research_game_metadata.py --no-verify-web
```

公开网页查证会并发请求，默认并发数是 6。如需降低请求压力：

```bash
python3 research_game_metadata.py --web-workers 2
```

## 不注册 BGG application 的情况

BGG 允许登录后下载自己的 collection，不需要注册 application。这个模式只能同步 collection 里直接返回的基础信息，需要提供登录 cookie，并跳过详情接口：

```bash
python3 sync_bgg_collection.py --skip-details
```

如果要自动补游戏详情，例如排名、机制、重度、推荐人数、中文名候选等，仍然需要 BGG application token。

## 生成网页

`generate_html.py` 会读取 `data.json`，生成一个静态 HTML 表格页面。

基本用法：

```bash
python3 generate_html.py
```

默认输入是 `data.json`，默认输出是 `index.html`。

首次运行先安装依赖：

```bash
npm install
```

生成后启动本地测试服务器：

```bash
./development-server.sh
```

自定义输入、输出和标题：

```bash
python3 generate_html.py --data data.json --output index.html --title 桌游列表
```

生成的网页支持：

- 点击任意列标题排序，再点一次切换升序/降序。
- 拖拽列标题调整左右顺序，列顺序会保存在浏览器本地。
- 搜索名称、年份、机制、状态等表格内容。
- 游戏名直接链接到 BGG 页面；`id` 为空或 `bgg: false` 的条目不会生成链接。
- 用下拉多选筛选 Collection、BGG、ID 状态。
- 用机制下拉多选筛选游戏；选择多个机制时只显示同时包含这些机制的条目。
- 点击“打印”生成适合横向打印的表格。
