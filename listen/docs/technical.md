# Echo Listen — 技术文档

## 1. 目录结构

```
listen/
├── docs/
│   ├── design.md          # 设计文档
│   ├── technical.md       # 本文档
│   └── deploy.md          # 部署手册
└── web/                   # Cloudflare Pages 发布根目录
    ├── index.html
    ├── style.css
    ├── app.js
    ├── config.json        # R2 公开域名
    └── data/
        ├── catalog.json
        └── neg_explain/
            └── manifest.json
```

---

## 2. 数据文件规范

### 2.1 `config.json`

```json
{
  "r2_public_base": "https://pub-xxxxxxxx.r2.dev"
}
```

| 字段 | 说明 |
|------|------|
| `r2_public_base` | R2 桶的公开访问域名，**不含**末尾斜杠 |

前端会将 `r2_public_base` 与 manifest 中的 `audio_path` 拼接为完整 URL。

---

### 2.2 `catalog.json`

```json
{
  "series": [
    {
      "series_id": "neg_explain",
      "book_title": "反对阐释",
      "manifest": "/data/neg_explain/manifest.json"
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `series_id` | ✓ | 系列唯一 ID |
| `book_title` | ✓ | 展示用书名 |
| `manifest` | ✓ | manifest 的站点内路径 |

**多系列**：catalog 中增加条目；访问 `/?series=national_org` 指定系列。仅一个系列时可省略参数。

---

### 2.3 `manifest.json`

```json
{
  "series_id": "neg_explain",
  "book_title": "反对阐释",
  "updated_at": "2026-07-03",
  "episodes": [
    {
      "episode_id": "EP01",
      "title": "集标题",
      "central_question": "核心问题（可选，展示在播放器下方）",
      "duration_sec": null,
      "audio_path": "neg_explain/EP01.mp3",
      "published": true
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `episode_id` | ✓ | 稳定 ID，与 R2 文件名一致 |
| `title` | ✓ | 集标题 |
| `central_question` | | 副标题 |
| `duration_sec` | | 预留；当前由 `<audio>` 自动获取时长 |
| `audio_path` | * | R2 对象键，相对 bucket 根路径 |
| `audio_url` | * | 完整 URL；若存在则优先于 `audio_path` |
| `published` | ✓ | 仅 `true` 的集会出现在页面 |

`audio_path` 与 `audio_url` 二选一即可。推荐 `audio_path` + 统一 `config.json`，换桶时只改一处。

**R2 路径约定**：`{series_id}/{episode_id}.mp3`，例如 `neg_explain/EP01.mp3`。

---

## 3. 前端实现

### 3.1 加载顺序

```
config.json ──┐
              ├──→ 解析系列 → manifest.json → 渲染列表
catalog.json ─┘
```

### 3.2 播放器

使用原生 `<audio controls>`：

- 进度拖动、暂停：浏览器原生支持（依赖 R2 的 HTTP Range）
- 预加载：`preload="metadata"`，减少首屏流量

### 3.3 续播逻辑

| 事件 | 行为 |
|------|------|
| `loadedmetadata` | 若 localStorage 有进度且小于时长，设置 `currentTime` |
| 播放中 | 每 5 秒写入 localStorage |
| `pause` | 立即写入 |
| 切换集 | 先保存当前集进度，再加载新集 |
| `ended` | 清除该集进度记录 |

Storage Key：`echo:progress:{series_id}:{episode_id}`  
值：秒数（浮点字符串）

### 3.4 URL 参数

| 参数 | 示例 | 说明 |
|------|------|------|
| `series` | `?series=neg_explain` | 指定系列（多系列时必填） |
| `ep` | `?ep=EP03` | 启动时自动选中该集（须已发布） |

---

## 4. 本地开发

在项目根目录启动静态服务器，以 `listen/web` 为根：

```bash
cd listen/web
python -m http.server 8080
```

浏览器打开 `http://localhost:8080`。

**注意**

- 未配置 R2 或 MP3 未上传时，页面可正常显示列表，但播放会 404
- 本地调试可临时把某一集 `published` 设为 `true`，并将 `audio_url` 指向可访问的测试 URL

---

## 5. Cloudflare 组件说明

| 组件 | 用途 |
|------|------|
| **Pages** | 托管 `web/` 静态文件，绑定 Git 自动部署 |
| **R2** | 存储 MP3，开启 Public Access 提供 `*.r2.dev` 域名 |

Pages 与 R2 在同一 Cloudflare 账号下，无需 CORS 配置（音频 URL 为跨域，但 `<audio>` 不受 CORS 限制）。

---

## 6. 新增系列 checklist

1. 在 R2 创建前缀 `{series_id}/`，上传 MP3
2. 新建 `web/data/{series_id}/manifest.json`
3. 在 `catalog.json` 增加条目
4. `git push`

---

## 7. 从 outline.json 生成 manifest（可选）

仓库内 EP 元数据来源于 `asset/{series}/outline.json`。当前 manifest 已预生成；若 outline 有变，可重新运行：

```bash
python -c "
import json
from pathlib import Path

series = 'neg_explain'
outline = json.loads(Path(f'asset/{series}/outline.json').read_text(encoding='utf-8'))
episodes = [{
    'episode_id': ep['episode_id'],
    'title': ep['title'],
    'central_question': ep['central_question'],
    'duration_sec': None,
    'audio_path': f'{series}/{ep[\"episode_id\"]}.mp3',
    'published': False,
} for ep in outline['episodes']]

manifest = {
    'series_id': series,
    'book_title': outline['book_title'],
    'updated_at': 'YYYY-MM-DD',
    'episodes': episodes,
}
path = Path(f'listen/web/data/{series}/manifest.json')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
"
```

生成后手动将已上传 R2 的集设为 `"published": true`。

---

## 8. 故障排查

| 现象 | 可能原因 |
|------|----------|
| 暂无已发布的集数 | 所有集 `published` 均为 `false` |
| 请配置 r2_public_base | `config.json` 仍为占位符 |
| 播放 404 | R2 未上传或 `audio_path` 与对象键不一致 |
| 无法拖动进度 | R2 Public Access 未开或对象不存在 |
| 续播不生效 | 浏览器禁用 localStorage 或隐私模式 |
