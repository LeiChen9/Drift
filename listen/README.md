# Echo Listen

在线收听模块，与本地 TTS 流水线独立。基于 **Cloudflare Workers（静态资源）+ R2**，无传统后端服务器。

## 文档

| 文档 | 说明 |
|------|------|
| [设计文档](docs/design.md) | 架构、原则、扩展路径 |
| [技术文档](docs/technical.md) | 数据格式、前端逻辑、本地开发 |
| [部署手册](docs/deploy.md) | Cloudflare 从零部署步骤 |

## 快速开始

1. 按 [部署手册](docs/deploy.md) 配置 R2 与 Pages
2. 编辑 `web/config.json` 填入 R2 公开域名
3. 上传 MP3 到 R2，将 manifest 中对应集 `published` 设为 `true`
4. `git push` 触发 Pages 部署

本地预览：

```bash
cd web
python -m http.server 8080
```

## 目录

```
listen/
├── docs/          # 文档
└── web/           # Pages 发布根目录
    ├── config.json
    └── data/      # catalog + manifest
```
