# Echo Listen — 部署手册

本手册面向首次部署：Cloudflare Pages（静态站点）+ R2（音频存储）。全程可在免费额度内完成。

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

1. 在 bucket 中 **Upload**
2. 路径规则：`{系列ID}/{集ID}.mp3`
   - 示例：`neg_explain/EP01.mp3`
3. 单集约 40MB，10 集约 400MB，远低于 R2 免费 10GB 上限

**验证**：浏览器直接打开  
`https://pub-xxx.r2.dev/neg_explain/EP01.mp3`  
应能下载或播放。

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

## 第三步：创建 Cloudflare Pages 项目

1. Dashboard → **Workers & Pages** → **Create**
2. 选 **Pages** → **Connect to Git**
3. 选择 Echo 仓库
4. 构建设置：

   | 项 | 值 |
   |---|---|
   | Project name | `echo`（自定） |
   | Production branch | `main`（或你的主分支） |
   | Framework preset | **None** |
   | Build command | *(留空)* |
   | Build output directory | **`listen/web`** |

5. **Save and Deploy**

部署完成后获得域名，例如：

```
https://echo.pages.dev
```

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
| **Cloudflare Pages** | 无限静态请求、500 次构建/月 | 一般 $0 |
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
- [ ] Pages 项目已连接仓库，输出目录 `listen/web`
- [ ] 浏览器验收播放与续播
