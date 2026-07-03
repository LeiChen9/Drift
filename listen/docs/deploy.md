# Echo Listen — 部署手册

本手册面向首次部署：**Cloudflare Workers 静态资源**（托管页面）+ **R2**（托管音频）。全程可在免费额度内完成。

---

## 前置条件

- Cloudflare 账号（[dash.cloudflare.com](https://dash.cloudflare.com)）
- 本仓库已推送到 GitHub（或 GitLab）
- 本地已有 MP3 文件（TTS 产出，建议命名为 `EP01.mp3` 等）

---

## 第一步：创建 R2 存储桶

1. 登录 Cloudflare Dashboard → **R2 Object Storage**
2. **Create bucket**
   - Bucket name：例如 `echo-audio`
   - Location：选 **Automatic** 或离听众较近的亚太区域
3. 进入 bucket → **Settings**
4. 找到 **Public Development URL** → **Enable**
5. 复制生成的域名，形如：
   ```
   https://pub-xxxxxxxxxxxxxxxx.r2.dev
   ```
   记下此地址，后续写入 `config.json` 的 `r2_public_base`。

### 上传音频

**方式 A：控制台拖拽（小文件、网络好时可用）**

1. 在 bucket 中 **Upload**
2. 路径规则：`{系列ID}/{集ID}.mp3`
   - 示例：`neg_explain/EP01.mp3`
3. 单集约 40MB，10 集约 400MB，远低于 R2 免费 10GB 上限

**方式 B：Wrangler 命令行（推荐，24MB+ 更稳）**

控制台上传在国内网络下容易超时或中途失败，改用 CLI：

```bash
cd listen
npx wrangler login
npx wrangler r2 object put echo-audio/neg_explain/EP01.mp3 --file="D:/Code/Echo/output/neg_explain/EP01.mp3" --remote --content-type audio/mpeg
```

- 把 `echo-audio` 换成你的 bucket 名
- 把 `--file` 换成本地 MP3 路径
- **`--remote` 必加**，否则只写到本地模拟，不会进云端
- Wrangler 单文件上限约 315MB，40MB 没问题

**验证**：浏览器直接打开  
`https://pub-xxx.r2.dev/neg_explain/EP01.mp3`  
应能下载或播放。

### 控制台上传失败？常见原因

| 原因 | 表现 | 处理 |
|------|------|------|
| **网络超时**（国内最常见） | 传到一半失败、无明确错误 | 用上面的 **Wrangler CLI** |
| **R2 未正确开通** | 无法建 bucket / 点上传无反应 | Dashboard → Billing，确认 R2 已订阅（$0 也要绑卡）；或访问 [r2 计算器页](https://r2-calculator.cloudflare.com/) 点 Get started |
| **文件名过长/含特殊字符** | 个别文件失败 | 统一命名为 `EP01.mp3`，上传后在 R2 里放到 `neg_explain/` 前缀下 |
| **浏览器插件干扰** | 随机失败 | 换 Chrome 无痕模式，或换浏览器 |
| **单文件过大用错 API** | 很大文件报 501 | 40MB 一般不是这个问题；超大文件用 rclone |

**快速自检**：先上传一个 **1MB 以内的测试 mp3**。若小文件成功、24MB 失败 → 基本是网络/超时，用 CLI 即可。

---

## 第二步：配置仓库

编辑 `listen/web/config.json`：

```json
{
  "r2_public_base": "https://pub-你的ID.r2.dev"
}
```

编辑 `listen/web/data/neg_explain/manifest.json`：将已上传 R2 的集设为 `"published": true`。

示例：

```json
{
  "episode_id": "EP01",
  "title": "...",
  "central_question": "...",
  "duration_sec": null,
  "audio_path": "neg_explain/EP01.mp3",
  "published": true
}
```

提交并 push：

```bash
git add listen/
git commit -m "Add Echo listen site"
git push
```

---

## 第三步：部署静态站点（Workers + Git）

Cloudflare 已将 Pages 合并进 **Workers**。新版控制台里往往**没有单独的 Pages 选项**，只有 **Create application**；默认 Deploy command 为 `npx wrangler deploy`——**这就是正确流程**，不是配错了。

仓库里已包含 `listen/wrangler.jsonc`，会把 `listen/web/` 作为静态资源目录上传。

### 3.1 创建并连接 Git

1. Dashboard → **Workers & Pages** → **Create application**
2. 选 **Connect to Git** / **Import an existing Git repository**（文案因账号而异）
3. 授权 GitHub，选择 Echo 仓库
4. 构建设置：

   | 项 | 值 | 说明 |
   |---|---|---|
   | Application / Project name | `echo-listen`（自定） | 与 `wrangler.jsonc` 里 `name` 一致更好 |
   | Production branch | `main` | 你的主分支 |
   | Root directory (Path) | **`listen`** | **重要**：让 Wrangler 读到 `wrangler.jsonc` |
   | Build command | **`npx wrangler deploy`** | 保持默认即可 |
   | Build output directory | *(留空或忽略)* | 由 `wrangler.jsonc` 的 `assets.directory` 决定 |

5. **Save and Deploy**

### 3.2 `wrangler.jsonc` 做了什么

```jsonc
{
  "name": "echo-listen",
  "compatibility_date": "2026-07-03",
  "assets": {
    "directory": "./web"
  }
}
```

- 无 Worker 脚本，纯静态托管（HTML / JS / JSON）
- 等价于旧版 Pages 的 Build output = `web`（在 Path=`listen` 前提下）

### 3.3 部署完成后

访问域名形如：

```
https://echo-listen.<你的子域>.workers.dev
```

在 Workers & Pages 项目页可看到准确 URL（有时也显示 `*.pages.dev`，以控制台为准）。

### 3.4 若仍能看到 Pages 标签（旧版界面）

部分账号仍有 **Workers | Pages** 两个标签。若选 Pages：

| 项 | 值 |
|---|---|
| Framework preset | None |
| Build command | 留空，或 `exit 0` |
| Build output directory | `listen/web`（Path 留空时） |

两种路径最终效果相同：托管 `listen/web/` 里的静态文件。

### 3.5 本地手动部署（可选，不连 Git）

```bash
cd listen
npx wrangler login
npx wrangler deploy
```

需已安装 Node.js。适合快速试部署，日常仍推荐 Git 自动部署。

### 3.6 常见误区

| 现象 | 说明 |
|------|------|
| 找不到 Pages 选项 | 正常，用 Workers + `wrangler deploy` 即可 |
| 只有 Create application | 点进去后选 Connect Git，不要选纯 Worker 模板（除非能改 Path） |
| 部署后 404 | Path 未设为 `listen`，或 `web/index.html` 不存在 |
| `wrangler.jsonc` 未生效 | Root directory 必须是 `listen`，不是仓库根 |

---

## 第四步：验收

1. 打开 Pages 域名，应看到系列标题「反对阐释」和已发布集列表
2. 点击 EP01 → 播放器加载 → 可播放、拖动进度条
3. 暂停后刷新页面 → 应从相近位置续播
4. 手机浏览器重复以上步骤

---

## 日常更新流程

### 发布新集

1. TTS 产出 → 重命名为 `EPxx.mp3`
2. 上传到 R2：`neg_explain/EPxx.mp3`
3. manifest 中对应条目 `"published": true`
4. `git push` → Pages 自动重新部署（仅 JSON 变更，秒级完成）

### 仅更新音频（不改 metadata）

直接覆盖 R2 上同名文件即可，无需 redeploy Pages。

### 修改标题等 metadata

改 manifest → `git push`。

---

## 费用说明

| 服务 | 免费额度（个人足够） | 你可能关心的 |
|------|----------------------|--------------|
| **Cloudflare Workers（静态资源）** | 托管 HTML/JS/JSON | 免费额度内一般 $0 |
| **R2 存储** | 10 GB·月 | 1G 音频 ≪ 10G |
| **R2 出站流量** | **免费** | 听众下载 MP3 不额外收 egress 费 |

无需购买 OSS、Railway 或 VPS。

---

## 可选：绑定自定义域名

若以后有域名并完成备案：

1. Pages 项目 → **Custom domains** → 添加域名
2. 按提示在 DNS 添加 CNAME

R2 也可绑定自定义域名（R2 bucket → Settings → Custom Domains），届时更新 `config.json` 中的 `r2_public_base`。

---

## 可选：本地预览

```bash
cd listen/web
python -m http.server 8080
# 打开 http://localhost:8080
```

需已配置有效的 `r2_public_base` 且 R2 上已有对应 MP3。

---

## 常见问题

### Q: 页面显示「暂无已发布的集数」

所有集的 `published` 都是 `false`。把已上传 R2 的改为 `true` 并 push。

### Q: 显示「请配置 r2_public_base」

`config.json` 里仍是 `pub-REPLACE_ME.r2.dev`，改成真实 R2 公开域名。

### Q: 点击播放没声音 / 404

- 检查 R2 是否启用 Public Development URL
- 检查对象路径是否与 `audio_path` 一致（区分大小写）
- 浏览器 Network 面板查看 MP3 请求状态码

### Q: 国内访问慢

Cloudflare 免费节点在国内无保证。若以后需要优化，可将 `audio_url` 改为国内 CDN/OSS 地址，Pages 仍可托管页面。

### Q: 能否把 MP3 也放进 Git？

不推荐。单文件 ~40MB 会膨胀仓库，且 Pages 不适合分发大文件。应用 R2。

---

## 部署 checklist

- [ ] R2 bucket 已创建
- [ ] Public Development URL 已启用
- [ ] MP3 已上传到 `neg_explain/EPxx.mp3`
- [ ] `config.json` 已填写真实 `r2_public_base`
- [ ] manifest 中已发布集 `published: true`
- [ ] 代码已 push 到 Git
- [ ] Workers 项目已连接仓库，**Path = `listen`**，Deploy = `npx wrangler deploy`
- [ ] 浏览器验收播放与续播
