# Echo Listen — 设计文档

## 1. 背景与目标

Echo 项目的核心流水线（rewrite → TTS）在本地运行，与在线收听无关。Listen 模块是一个**独立的分发层**，让听众通过浏览器收听已生成的播客音频。

**目标**

- 听众在网页选集、播放、拖动进度、暂停后续播
- 零后端服务器：静态站点 + 对象存储
- 个人阶段成本尽量为 $0（Cloudflare 免费额度内）
- 与 `rewriter.py`、`tts.py` 完全解耦，便于以后扩展

**非目标（首版）**

- 用户账号、付费、评论
- 在线 TTS 或台本编辑
- RSS / 播客 App 订阅
- 服务端播放进度同步

---

## 2. 设计原则

| 原则 | 说明 |
|------|------|
| 生产与分发分离 | TTS 在本地；线上只托管 HTML 与 MP3 |
| 静态优先 | 无 FastAPI、无数据库；manifest 即目录 |
| 契约驱动 | `catalog.json` + `manifest.json` + `config.json` 定义全部行为 |
| 按需发布 | `published: false` 的集不会出现在页面 |
| 可扩展 | 加系列 = 加 manifest；加功能 = 改前端或加 Workers |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  本地（你的电脑）                                         │
│  rewriter.py → tts.py → output/*.mp3                     │
│       ↓ 手动上传                                         │
└───────┼─────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────┐         ┌──────────────────────────┐
│ Cloudflare R2     │         │ Cloudflare Pages         │
│ neg_explain/      │         │ index.html, app.js       │
│   EP01.mp3 ...    │         │ config.json, manifest    │
└─────────┬─────────┘         └────────────┬─────────────┘
          │                                │
          │  音频 Range 请求                │  页面 + JSON
          └────────────┬───────────────────┘
                       ▼
                 听众浏览器
                 <audio> + localStorage 续播
```

**流量特征**

- Pages：体积极小（HTML/JS/JSON），Git push 即更新
- R2：承载全部 MP3 流量（约 40MB/集），免费额度 10GB 存储、出站免费

---

## 4. 内容模型

### 4.1 配置文件 `web/config.json`

全局唯一需改的部署参数：R2 公开访问域名。

### 4.2 系列目录 `web/data/catalog.json`

列出所有系列及其 manifest 路径。多系列时通过 URL `?series=xxx` 切换。

### 4.3 单系列 manifest `web/data/{series_id}/manifest.json`

每集一条记录，控制是否上线及音频路径。

---

## 5. 听众体验

1. 打开 Pages 域名（如 `https://echo.pages.dev`）
2. 页面加载 catalog → manifest → 渲染已发布集列表
3. 点击某一集 → `<audio>` 从 R2 拉流播放
4. 暂停或关闭页面 → 进度写入 `localStorage`
5. 再次打开同一集 → 自动从上次位置续播

续播 Key 格式：`echo:progress:{series_id}:{episode_id}`

---

## 6. 发布流程（运营视角）

```
TTS 完成
  → 重命名为 EPxx.mp3
  → 上传到 R2 bucket 的 neg_explain/ 前缀
  → 编辑 manifest.json：published 改为 true
  → git push → Pages 自动部署
```

无需单独跑发布脚本；manifest 手改即可。

---

## 7. 扩展路径

| 需求 | 做法 |
|------|------|
| 新系列 | 新增 `data/{id}/manifest.json` + catalog 条目 |
| 文稿 | manifest 加 `script_url`，前端加 Tab |
| 播放统计 | Cloudflare Workers 打点 |
| 鉴权 | R2 签名 URL + Workers 鉴权 |
| 国内加速 | 以后可迁音频到国内 OSS，manifest 改 URL 即可 |

---

## 8. 已知限制

- Cloudflare 在国内访问速度不稳定，个人收听通常可接受
- 续播仅存于当前浏览器，换设备不同步
- R2 公开桶需注意不要上传非公开内容
- `config.json` 中的 R2 域名会暴露在前端（公开音频本就需公开 URL）

---

## 9. 与 Echo 主仓库的关系

```
Echo/
├── rewriter.py, tts.py, output/   ← 生产流水线（本地）
└── listen/                        ← 在线收听（Cloudflare）
    ├── web/                       ← Pages 发布目录
    └── docs/                      ← 文档
```

两者仅通过「你手动上传 MP3 + 维护 manifest」衔接，代码无 import 依赖。
