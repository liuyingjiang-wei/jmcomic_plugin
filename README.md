# jmcomic-plugin

禁漫天堂（JMComic）搜索、下载、PDF 导出，以及 QQ 群 `#车牌` 指令。基于 [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)。
**插件名：** `jmcomic` · **版本：** 1.1.0 · **类型：** 能力插件（HTTP + Agent 工具 + OneBot 指令，非消息桥接）

---

## 目录

- [在 LY-NEXT 中的位置](#在-ly-next-中的位置)
- [架构](#架构)
- [依赖与安装](#依赖与安装)
- [配置](#配置)
- [HTTP API](#http-api)
- [Agent 工具](#agent-工具)
- [QQ `#车牌` 指令](#qq-车牌-指令)
- [`jm帮助` 指令](#jm帮助-指令)
- [验证与排错](#验证与排错)

---

## 在 LY-NEXT 中的位置

本插件通过 `LyNextPlugin` 接入 core，与 `qq-onebot` 桥接插件配合使用（`#车牌` 需要 OneBot 会话 API）。

| 注册点 | 实现 |
|--------|------|
| `register_tools` | `jmcomic_search` · `jmcomic_download` |
| `register_apis` | `/api/jmcomic/*`（`PluginRouterAPI`） |
| `on_startup` | 挂载静态目录 `/media` → `data/media/` |
| OneBot 扩展 | `register_onebot_command_handler`（`ly_next.messaging.onebot_commands`） |
| Telegram 扩展 | `register_telegram_command_handler`（`ly_next.messaging.telegram_commands`） |

安装目录：`plugins/local/jmcomic_plugin/`。

---

## 依赖与安装

### 目录说明

| 路径 | 是什么 |
|------|--------|
| `ly-next/` | **项目根目录**（有 `pyproject.toml`、`ly_next/`）— 安装命令在这里执行 |
| `ly-next/plugins/local/jmcomic_plugin/` | **插件源码目录**（你当前可能在的子目录）— 只放代码，不要在这里单独 `pip install` |

`/path/to/ly-next` 只是文档占位符，请换成你机器上的真实路径。例如本仓库常见为：

- Git Bash / MINGW64：`/d/code/code/ly-next`
- PowerShell / CMD：`D:\code\code\ly-next`

### 第一步：进入项目根目录

**不要**在 `jmcomic_plugin` 里执行安装。先回到根目录：

```bash
# 若你正在 plugins/local/jmcomic_plugin 里（Git Bash）
cd ../../..

# 或直接切到根目录（按你的实际路径改）
cd /d/code/code/ly-next
```

确认当前目录正确（应能看到 `pyproject.toml`）：

```bash
ls pyproject.toml plugins/local/jmcomic_plugin/requirements.txt
```

### 第二步：安装插件额外依赖

LY-NEXT 主项目用 `uv` 管理虚拟环境。在**项目根目录**执行：

```bash
uv pip install -r plugins/local/jmcomic_plugin/requirements.txt
```

等价写法（PowerShell 也可用同一条，路径用引号包起来）：

```powershell
cd D:\code\code\ly-next
uv pip install -r plugins/local/jmcomic_plugin/requirements.txt
```

若尚未初始化过主项目环境，先执行一次：

```bash
uv sync
```

再安装插件依赖。

### 第三步：确认装上了

```bash
uv pip show jmcomic
uv run python -c "import jmcomic; print('jmcomic ok', jmcomic.__version__)"
```

### 第四步：重启 LY-NEXT

```bash
uv run ly --no-prompt
```

在 **设置 → 基础设施** 或 `GET /api/system/extensions` 的 `plugins` 列表中应出现 `jmcomic`。

### `requirements.txt` 里有什么

| 包 | 用途 |
|----|------|
| `jmcomic>=2.6.0` | 站点搜索、相册下载（**插件核心，必须装**） |
| `img2pdf>=0.5.0` | jmcomic 内置 `img2pdf` 插件依赖，**导出 PDF / `#车牌` 必须装** |
| `PyYAML>=6.0` | 读写 `data/jmcomic/config.yaml`（主项目通常已带 PyYAML，写上是为了独立 pip 安装时不缺依赖） |

### 常见错误

| 现象 | 原因与处理 |
|------|------------|
| `cd: /path/to/ly-next: No such file or directory` | 复制了占位路径；改成你的真实根目录，如 `cd /d/code/code/ly-next` |
| `No such file or directory: plugins/local/jmcomic_plugin/requirements.txt` | 当前不在项目根目录；先 `cd` 到含 `pyproject.toml` 的那一层 |
| 插件列表没有 `jmcomic` | 确认 `plugins/local/jmcomic_plugin/` 存在且 `plugins.enabled: true`，然后重启 |
| `ModuleNotFoundError: jmcomic` | 未执行第二步，或装到了别的 Python 环境；务必在根目录用 `uv pip install -r ...` |
| 日志 `插件 img2pdf 依赖库: img2pdf` / `PDF export finished but output file was not found` | 未装 `img2pdf`；重新执行 `uv pip install -r plugins/local/jmcomic_plugin/requirements.txt` 后重启 |

---

## 配置

配置合并顺序（后者覆盖前者）：

1. 插件内置默认值（`config.py`）
2. **`data/jmcomic/config.yaml`**（首次运行从 `default_config.yaml` 复制）
3. **`plugins.jmcomic`**（写在 `data/ly_next/config.yaml` 中，可选）

### 无代理环境（重要）

[jmcomic 官方配置](https://jmcomic.readthedocs.io/zh-cn/latest/option_file_syntax/)：

| `client.impl` | 说明 |
|---------------|------|
| `api` | APP 端，**不限 IP，无代理时推荐** |
| `html` | 网页端，部分地区受限 |

默认 `use_system_proxy: false`，避免读取本机 Clash 等系统代理导致连接失败。

```yaml
plugins:
  jmcomic:
    download_dir: "data/jmcomic/download"
    pdf_dir: "data/jmcomic/pdf"
    delete_original: true
    reuse_existing_pdf: true
    public_base_url: ""          # 群文件发送失败时的 PDF 直链根地址
    client:
      impl: api
      proxy: ""
      use_system_proxy: false
    qq:
      chepai_enabled: true
      recall_delay_sec: 120      # 30–3600
      download_timeout_sec: 600  # 60–3600
```

| 项 | 说明 |
|----|------|
| `delete_original` | PDF 导出成功后删除原始图片目录 |
| `reuse_existing_pdf` | 本地已有 PDF 时跳过下载 |
| `public_base_url` | 留空时依次尝试 `server.public_url` / `server.url` / `host:port`（loopback 不会用于外网直链） |
| `qq.chepai_enabled` | 是否响应 `#车牌{数字}` |
| `qq.recall_delay_sec` | 处理完成后撤回「正在处理…」等提示消息的延迟（秒） |

---

## HTTP API

挂载前缀：**`/api/jmcomic`**（需 API Key，与工作台鉴权一致）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/jmcomic/search?q=关键词&page=1` | 站内搜索；失败 502 |
| POST | `/api/jmcomic/download` | Body: `{"album_id":"123456"}`；非法 ID 400；其它错误返回 `{ok:false, error:…}` |
| GET | `/api/jmcomic/file?path=…` | 下载 PDF；路径须落在 `pdf_dir` 内 |

示例：

```bash
curl -H "X-API-Key: YOUR_KEY" \
  "http://127.0.0.1:8000/api/jmcomic/search?q=keyword&page=1"

curl -X POST -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"album_id":"123456"}' \
  "http://127.0.0.1:8000/api/jmcomic/download"
```

---

## Agent 工具

| 工具 | 参数 | 返回 |
|------|------|------|
| `jmcomic_search` | `query`, `page=1` | 搜索结果 dict |
| `jmcomic_download` | `album_id` | `{ok, cached, pdf_path, size, …}` |

分类：`media`。在 ReAct / Plan 等带工具的模式下，Agent 可直接调用；纯 `chat` 模式不会挂载工具。

---

## QQ `#车牌` 指令

**前置：** 同时加载 `qq-onebot` 与本插件；NapCat 已连上 LY-NEXT（见 [QUICKSTART 路径 ③](../../../docs/QUICKSTART.md)）。

群内或私聊发送（**无需 @ 机器人**）：

```
#车牌123456
```

| 特性 | 说明 |
|------|------|
| 触发格式 | `#车牌` + 数字相册 ID（不区分大小写） |
| 与 auto_reply 关系 | 在 `bridge.onebot11.auto_reply.enabled: false` 时仍可用 |
| 处理优先级 | `priority=50`，在通用自动回复之前由 `onebot_commands` 分发 |

---

## `jm帮助` 指令

在 **QQ**（群聊/私聊，无需 @）或 **Telegram 私聊** 发送以下任一文本，即可获取本插件用法说明（非工作台面板）：

```
jm帮助
jm 帮助
jm help
/jm帮助
```

| 渠道 | 说明 |
|------|------|
| QQ | 经 `onebot_commands` 分发，`priority=40`，在 `#车牌` 之前匹配 |
| Telegram | 插件启动时挂载 `telegram_commands` 钩子，不修改 `telegram_bot` 源码 |
| 与 auto_reply | QQ 侧在 `@` / 前缀检查之前处理，关闭自动回复时仍可用 |

---

## 验证与排错

```bash
uv run ly --no-prompt
curl -H "X-API-Key: …" http://127.0.0.1:8000/api/system/extensions
# 响应 plugins 列表中应含 jmcomic
```

| 现象 | 排查 |
|------|------|
| 插件未加载 | `plugins.enabled: true`；`plugins/local/jmcomic_plugin/` 存在；`uv pip install -r …/requirements.txt` |
| 搜索/下载超时 | 改 `client.impl: api`；确认 `use_system_proxy: false` 或显式 `proxy` |
| `#车牌` 无响应 | 确认 `qq-onebot` 已连接；`qq.chepai_enabled: true` |
| `jm帮助` 无响应（TG） | 确认 `telegram_bot` 与本插件均已加载；重启后插件会挂载 TG 命令钩子 |
| 群聊收不到 PDF | 配置 `public_base_url` 为公网可访问地址；检查 `data/media/jmcomic/` 是否生成文件 |
| Agent 调不到工具 | 场景需为 ReAct/Plan 等工具模式，非「通用助手」纯 chat |

---

## 相关文档

- [LY-NEXT README](../../../README.md) — 总览与架构
- [plugins/README.md](../../README.md) — 插件安装方式
- [TECHNICAL.md](../../../TECHNICAL.md) — 对话链路与 OneBot 扩展点
# jmcomic_plugin
