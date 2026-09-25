# 小范围内测部署

## 架构

```text
微信小程序 → HTTPS/Caddy → FastAPI（单实例） → SQLite + 私有媒体卷
                                      └→ 私网 FASHN VTON GPU Worker
```

该配置面向 10–30 人的小范围内测。SQLite 只运行一个 API 实例；需要水平扩容时必须迁移到 MySQL/PostgreSQL 和独立对象存储。

## 准备

1. 复制 `.env.example` 为 `.env`，生成至少 32 字符的随机 `AUTH_TOKEN_SECRET` 和独立 `FASHN_WORKER_TOKEN`。
2. 填写正式微信 AppID/AppSecret。AppSecret 只存在服务器环境变量中。
3. 准备已备案域名，将 `PUBLIC_DOMAIN` 指向服务器。
4. 把 `miniprogram/env.js` 的 `useMock` 改为 `false`，并把 `baseUrl` 改成后端 HTTPS 域名（不含 `/api/v1`）。
5. 在小程序后台登记 request、uploadFile、downloadFile 合法域名。
6. 在具备 NVIDIA Container Toolkit、Ampere 或更新架构 GPU 的主机准备 FASHN 权重目录。
7. 配置真实 `BODY_SCAN_PROVIDER`、`CONTENT_SAFETY_PROVIDER` 和 `REALTIME_PROVIDER`；生产预检会拒绝模拟 Provider。
8. 按 [隐私与提审配置](privacy-and-review.md) 完成公众平台声明。

## 启动

```bash
docker compose -f compose.production.yml --profile gpu up -d --build
```

首次启动后检查：

```bash
curl https://你的域名/health
docker compose -f compose.production.yml logs --tail=200 api fashn-worker caddy
```

## 发布闸门

```bash
python scripts/preflight.py
cd server
python -m ruff check app tests ../workers/fashn_vton/app.py
python -m pytest -q
```

`preflight.py` 只检查静态配置，不能代替微信开发者工具、真机、隐私协议、模型效果与数据删除测试。

## 备份与删除

内测阶段至少每日备份 `/data/taste-yourself.db`。媒体卷包含用户衣服、人像与生成图，不得进入普通日志或公开备份。账号级删除接口已经覆盖数据库记录与关联媒体；成功测量后的原始扫描帧会立即清除。本人定格照默认保留 7 天，生成结果默认保留 30 天，服务启动时自动清理；调整期限时需同步更新隐私指引。
