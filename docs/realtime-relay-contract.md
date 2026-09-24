# 15 秒实时中继合同

FastAPI 在 `REALTIME_PROVIDER=http` 时向 `REALTIME_SESSION_URL` 发起服务端请求：

```json
{
  "experience_session_id": "...",
  "garment_id": "...",
  "max_duration_seconds": 15
}
```

中继返回：

```json
{
  "id": "relay-session-id",
  "publish_url": "rtmp://或微信组件支持的推流地址",
  "play_url": "rtmp://或微信组件支持的播放地址",
  "client_token": "可选短期凭证"
}
```

要求：

- `publish_url` 和 `play_url` 必须能由微信小程序 `live-pusher` / `live-player` 直接使用，不能把只适用于浏览器的 WebRTC SDP 接口原样返回。
- 中继必须在自身服务端强制 15 秒租约，过期立即断开上游模型和流媒体资源；不能只依赖小程序倒计时。
- URL/凭证必须一次性、短期、绑定会话，供应商长期密钥不得返回小程序。
- 模型供应商若只提供浏览器 WebRTC，需要中继完成协议转换、鉴权和视频帧编解码。
- 中继创建失败或未返回完整推/拉流地址时，API 返回不可用，客户端保留静态试穿能力。

开发环境 `mock` 只验证交互和 15 秒倒计时，不上传视频；`disabled` 用于未取得微信类目权限的体验版。
