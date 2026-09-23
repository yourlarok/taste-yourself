# Taste Yourself

> AI 实时视频试穿 —— 打开摄像头，选一件衣服，动起来，衣服自然跟着你动。

微信小程序 MVP 项目开发文档。本文档是当前阶段的唯一权威开发依据，随架构决策持续更新。

---

## 1. 产品概述

### 1.1 一句话定位

基于实时生成式视频模型（Decart Lucy VTON）的微信小程试衣间：用户开启摄像头后可自由走动、转身，所选衣服实时、自然地穿在身上。

### 1.2 核心体验（MVP 范围）

| 功能 | 说明 | 优先级 |
|---|---|---|
| 实时试穿 | 摄像头画面实时换穿所选衣服，单次会话默认 15 秒 | P0 |
| 静态精修试穿 | 选衣后先生成一张高保真试穿图（低成本默认动作） | P0 |
| 我的衣橱 | 拍照/相册导入衣服图，自动清洗后入库复用 | P0 |
| 分享卡片 | 截取试穿帧生成精修图，带 AI 标识水印，可转发 | P1 |
| 使用额度 | 每日免费动态试穿次数封顶，成本可控 | P1 |

### 1.3 非目标（本阶段不做）

- 尺码推荐 / 合身度评估（"看起来如何"与"合不合身"是两个问题，本阶段只做前者）
- App、线下门店硬件
- 自研模型（API 优先，账单达到阈值后再评估自研蒸馏路线）

---

## 2. 关键技术决策

### 2.1 模型服务：Decart Lucy VTON 3.5（商用 API）

| 项目 | 规格 |
|---|---|
| 实时模式 | $0.02 / 活跃生成秒（720p，30fps，端到端延迟 <40ms） |
| 离线视频 | $0.04 / 生成秒 |
| 静态图（Lucy Image 2） | $0.02 / 张 |
| 接入方式 | WebRTC 实时流 + 短期 client token（API key 不下发前端） |
| 官方文档 | https://docs.platform.decart.ai |

### 2.2 为什么是小程序原生而不是 H5

已明确决策：直接使用微信小程序开发生态。**必须首先解决的前置门槛：**

- 小程序不支持标准 WebRTC，实时音视频只能使用微信原生组件 `live-pusher`（推流）/ `live-player`（播放）
- 这两个组件**仅对特定行业类目的认证企业主体开放**，需在 mp.weixin.qq.com 申请"实时音视频"类目。**这是项目的最高优先级风险，M1 第一天就要提交类目申请**
- 若类目申请失败，降级方案：小程序内嵌 web-view 加载 H5（需企业主体小程序 + 业务域名备案），H5 内走标准 WebRTC

### 2.3 视频流链路（小程序方案）

```
小程序 live-pusher ──RTC──→ 腾讯云 TRTC
                                │ 服务器旁路拉流
                                ▼
                        流媒体中转服务（自建）
                                │ WebRTC
                                ▼
                        Decart Lucy VTON 3.5
                                │ 处理后流
                                ▼
                        流媒体中转服务 ──RTC──→ 小程序 live-player 播放
```

- 控制信道（切换衣服、上传 prompt）走 WebSocket，与视频流分离
- 预期端到端延迟：约 0.8–1.5 秒（小程序 RTC + 中转转码 + 跨境链路），可接受，但需内测验证"镜子慢半拍"的体感
- 跨境链路稳定性是已知风险：中转服务器建议部署在香港/新加坡，同时启动与 Decart 的亚太节点商务沟通

### 2.4 脏衣服图清洗流水线（核心假设：用户给的图不干净）

用户上传的可能是"床上一件皱 T 恤、带杂物、光线差"。清洗在上传时离线执行一次，不进实时环路：

```
用户上传图
  → ① 服装提取：图像编辑/分割模型抠出衣服主体，置于纯白背景（≥512×512）
  → ② 描述词生成：视觉 LLM 读图生成结构化 prompt
       （"navy hoodie with white cross logo, zip front"）
  → ③ 质量校验：检测提取结果是否为有效服装（置信度低则提示用户重拍）
  → 存入衣橱（清洗图 + prompt + 原图）
```

- 试穿时调用：`Lucy VTON.set({ prompt, image: 清洗图 })`，参考图 + 描述词双信号，精度最高
- 候选提取服务：GPT-Image / Gemini 图像编辑 / 通义万相 / 开源 BiRefNet，M1 用商用 API 跑通，M2 评估开源替代降本

---

## 3. 系统架构

### 3.1 组件总览

| 组件 | 技术选型 | 职责 |
|---|---|---|
| 小程序端 | 微信原生（WXML/WXSS/TS） | 推流、播放、衣橱 UI、分享 |
| API 服务 | Node.js (NestJS) 或 Python (FastAPI)，M1 定稿时二选一 | 登录态、衣橱 CRUD、Decart token 签发、计费控制、清洗流水线编排 |
| 流媒体中转 | 腾讯云 TRTC + 自建转推服务（Node/Go + aiortc/mediasoup，M1 定稿） | 小程序流 ↔ Decart WebRTC 双向桥接 |
| 数据库 | MySQL 8.0 | 业务数据 |
| 缓存/队列 | Redis（会话状态、额度计数）+ 轻量任务队列（清洗任务） |  |
| 对象存储 | 腾讯云 COS | 原图、清洗图、分享卡片 |
| 内容安全 | 微信内容安全 API（mediaCheckAsync） | 用户上传图片与生成内容合规审核 |

### 3.2 成本控制设计（对应 API 按活跃秒计费）

| 策略 | 说明 |
|---|---|
| 静态优先 | 选衣服默认只生成静态试穿图（¥0.15/张），"动一下看看"才启动实时会话 |
| 15 秒会话 | 实时会话默认 15 秒后自动暂停，用户确认后续 15 秒 |
| 静止断流 | 检测到 3 秒无运动即冻结末帧并断开会话，运动恢复后自动重连 |
| 每日额度 | 每用户每日动态试穿次数封顶（内测期默认 3 次），Redis 计数 |
| 成本熔断 | 单日总成本超过阈值自动降级为纯静态模式，并告警 |

目标单位成本：典型用户 5 张静态图 + 2×15 秒动态 ≈ **¥3.5/人**（对比无节制使用 ¥28/人）。

---

## 4. 数据库设计（MySQL 8.0）

```sql
-- 用户
CREATE TABLE users (
  id            BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  openid        VARCHAR(64)  NOT NULL UNIQUE,      -- 微信 openid
  unionid       VARCHAR(64)  NULL,
  nickname      VARCHAR(64)  NULL,
  avatar_url    VARCHAR(512) NULL,
  status        TINYINT      NOT NULL DEFAULT 1,   -- 1正常 0封禁
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 衣橱（衣服）
CREATE TABLE garments (
  id              BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id         BIGINT UNSIGNED NOT NULL,
  raw_image_url   VARCHAR(512) NOT NULL,           -- 用户上传原图
  clean_image_url VARCHAR(512) NULL,               -- 清洗后白底图
  prompt          VARCHAR(1024) NULL,              -- LLM 生成的描述词
  category        VARCHAR(32)  NULL,               -- top/bottom/dress/...（LLM 识别）
  clean_status    TINYINT      NOT NULL DEFAULT 0, -- 0待清洗 1清洗中 2成功 3失败
  fail_reason     VARCHAR(255) NULL,
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_user (user_id, clean_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 试穿会话（每次静态生成或实时会话一条记录，用于计费与审计）
CREATE TABLE tryon_sessions (
  id             BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id        BIGINT UNSIGNED NOT NULL,
  garment_id     BIGINT UNSIGNED NOT NULL,
  mode           VARCHAR(16)     NOT NULL,         -- static / realtime
  duration_ms    INT UNSIGNED    NOT NULL DEFAULT 0, -- 实时会话活跃毫秒数
  cost_usd       DECIMAL(10,4)   NOT NULL DEFAULT 0, -- 本次 API 成本（美元）
  status         TINYINT         NOT NULL DEFAULT 0, -- 0进行中 1完成 2失败
  result_url     VARCHAR(512)    NULL,             -- 静态图/录制片段地址
  created_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user_time (user_id, created_at),
  KEY idx_cost (created_at, cost_usd)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 用户每日额度
CREATE TABLE daily_quotas (
  id              BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id         BIGINT UNSIGNED NOT NULL,
  quota_date      DATE           NOT NULL,
  realtime_used   INT UNSIGNED   NOT NULL DEFAULT 0, -- 已用动态次数
  realtime_limit  INT UNSIGNED   NOT NULL DEFAULT 3,
  static_used     INT UNSIGNED   NOT NULL DEFAULT 0,
  static_limit    INT UNSIGNED   NOT NULL DEFAULT 20,
  UNIQUE KEY uk_user_date (user_id, quota_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 分享卡片
CREATE TABLE share_cards (
  id          BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  user_id     BIGINT UNSIGNED NOT NULL,
  session_id  BIGINT UNSIGNED NOT NULL,
  image_url   VARCHAR(512)    NOT NULL,   -- 已加 AI 标识水印
  created_at  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

设计要点：

- `tryon_sessions.cost_usd` 逐笔记录 API 成本，是成本看板与熔断策略的数据源
- 额度以 (user_id, date) 为粒度，Redis 只做热计数，MySQL 为准
- 人像相关数据（会话流）不落库，仅结果图存 COS；原图保留策略需在隐私政策中明示

---

## 5. 合规清单（内测前必须完成）

| 事项 | 要求 | 状态 |
|---|---|---|
| 小程序实时音视频类目 | 企业主体申请 live-pusher/live-player 权限 | ☐ 未开始（最高优先级） |
| AI 生成内容标识 | 依《人工智能生成合成内容标识办法》，生成图/视频加显式标识 | ☐ 未开始 |
| 深度合成服务备案 | 依《互联网信息服务深度合成管理规定》评估备案义务 | ☐ 未开始 |
| 人脸信息保护 | 人脸属敏感个人信息：隐私政策单独告知 + 单独同意；人像出境传输需明示 | ☐ 未开始 |
| 内容安全审核 | 用户上传图 + 生成内容接入微信 mediaCheckAsync | ☐ 未开始 |
| 域名/小程序备案 | 服务器域名 ICP 备案、小程序备案 | ☐ 未开始 |

---

## 6. 里程碑

| 里程碑 | 目标 | 验收标准 |
|---|---|---|
| **M0 验证（1 周）** | 浏览器 demo 验证效果底线 | 调通 Decart quickstart；实测跳舞/转身/跳跃效果与脏图清洗精度，记录结论 |
| **M1 骨架（2-3 周）** | 类目申请 + 全链路打通 | 类目提交；小程序推流→中转→Decart→播放全链路跑通（UI 从简）；数据库与登录落地 |
| **M2 内测版（3-4 周）** | 可发内测 | 静态优先 + 15 秒动态 + 衣橱清洗 + 额度/熔断；100 人内测，预算 ≤ ¥3000 |
| **M3 迭代** | 依内测数据决策 | 分享裂变数据、留存、单用户成本达标后：小程序打磨 or App or B 端门店版 |

内测期关键观测指标：人均会话时长、动态功能点击率、分享率、单用户成本、跳舞场景效果差评率。

---

## 7. 风险登记

| 风险 | 等级 | 对策 |
|---|---|---|
| 实时音视频类目申请失败 | 高 | M1 第一天提交；降级方案为小程序 web-view 嵌 H5 |
| 跨境实时流不稳定/延迟高 | 高 | 中转节点放香港/新加坡；与 Decart 谈亚太节点；内测先记录延迟分布 |
| 激烈动作（跳舞/跳跃）效果穿帮 | 中 | M0 先行验证；预期管理（15 秒尝鲜定位）；分享图用静态精修兜底 |
| 脏图清洗失败率过高 | 中 | 多服务商 A/B；低置信度引导重拍 |
| API 成本失控 | 中 | 五级节流设计 + 日成本熔断 + 逐笔记账 |
| Decart 商务/合规不可用 | 中 | 跟踪国内实时视频模型进展（可灵/即梦/开源蒸馏），保留迁移接口抽象层 |
| 人脸数据出境合规 | 中 | 隐私政策明示 + 单独同意；评估国内中转脱敏方案 |

---

## 8. 仓库规划（随 M1 落地）

```
taste-yourself/
├── README.md            # 本文档
├── miniprogram/         # 微信小程序端
├── server/              # API 服务（登录/衣橱/计费/清洗编排）
├── relay/               # 流媒体中转服务（TRTC ↔ Decart WebRTC）
└── docs/                # 设计稿、API 协议、内测报告
```

技术栈最终选型（NestJS vs FastAPI、中转方案 aiortc vs mediasoup）在 M1 启动时以 ADR 形式补入 docs/。

---

## 9. Backlog（待办评估项）

### 9.1 尺码推荐（难题，需准确率 + 成本路线评估）

**问题本质**：试穿解决"看起来如何"，尺码解决"合不合身"。行业最好水平 top-1 准确率也仅 70–80%，目标应定为"显著降低退货率"而非"完美准确"。

| 路线 | 做法 | 准确率预期 | 成本 | 评估 |
|---|---|---|---|---|
| A. 问卷 + 尺码表映射 | 身高/体重/常穿尺码 → 品牌尺码表规则匹配 | 低-中（约 60%），品牌间尺码差异大 | 近零（纯规则 + 尺码表数据录入） | M2 即可上，做基线 |
| B. 照片身体测量 | 用户拍 1-2 张全身照 → 测量模型出围度（对标 3DLOOK/Presize） | 关键围度 ±1-2cm，准确率中-高 | 商用 API 约 $0.5-1/次；自研需采标训练 | 体验有摩擦（专门拍照），但数据可复用于推荐 |
| C. 购买/合身反馈协同 | "这件 M 合身"反馈 → 用户-品牌尺码画像，逐步收敛 | 随数据量增长，冷启动差 | 近零边际成本 | 与 A 组合做长期资产，数据库需预留反馈表 |
| D. 试穿视频提取体型（自研亮点） | 复用试穿会话视频流，姿态估计 + SMPL 回归出体型参数 | 中（需验证），但零额外用户动作 | 开源模型（MediaPipe/HMR2.0）+ 推理算力 | 与主场景天然协同，是差异化方向；注意体型数据属敏感信息，合规前置 |

**初步结论**：M2 上线 A（问卷+尺码表）做基线并埋反馈点（C 的数据积累）；M3 立项验证 D（复用视频流，若可行则跳过 B 的拍照摩擦）；B 作为 D 失败时的保底。专项评估报告（含各路线实测准确率）列为 M3 课题。

### 9.2 衣服类型推荐（商业化价值高）

**定位**：基于用户衣橱与试穿行为，推荐"适合你的衣服类型/风格"，是后续导购变现（CPS 佣金）的入口。

**初期形态（M3，轻量化）**：

- 推荐结果以**卡片**呈现：类型/风格描述 + 参考图，**不带购买链接**
- 例："你试穿短款上衣停留最长——推荐试试「工装夹克」「廓形西装」" + 对应参考图卡片
- 参考图来源：合规图库 / AI 生成示意（需加 AI 标识）

**技术路线（低成本起步）**：

| 组件 | 方案 | 成本 |
|---|---|---|
| 风格标签 | 视觉 LLM 给衣橱衣服批量打标（风格/版型/场景） | 每件几分钱，清洗流水线顺带做 |
| 相似/搭配检索 | CLIP 类开源视觉 embedding + 向量检索（pgvector 即可，免新组件） | 近零 |
| 推荐理由 | LLM 基于用户行为 + 标签生成一句话推荐语 | 每次几分钱 |

**演进路径**：卡片（无链接）→ 接入品牌/电商 CPS 链接变现 → 与商家合作的"可试穿商品库"。数据资产（用户风格画像）从 M2 埋点开始积累。
