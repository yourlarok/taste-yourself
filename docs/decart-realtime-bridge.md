# Decart Lucy VTON realtime bridge

The mini-program uses one mirror page with a native `live-pusher` input and
`live-player` output. It does not load an H5 page.

`REALTIME_PROVIDER=decart` makes the API call the trusted media gateway at
`REALTIME_SESSION_URL`. The gateway is responsible for:

1. accepting the mini-program's short-lived publish stream;
2. connecting to Decart Lucy VTON (`lucy-vton-latest`) using its server-side key;
3. returning a mini-program-compatible `publish_url` and `play_url`;
4. force-closing both legs after 15 seconds.

The API sends `DECART_API_KEY` as a server-to-server header only. Never put it
in `miniprogram/env.js`, WXML, or any client bundle. The gateway response must
contain both URLs; browser-only WebRTC/SDP URLs are deliberately rejected.

## Configuration

```dotenv
REALTIME_PROVIDER=decart
REALTIME_SESSION_URL=https://your-media-gateway.example.com/v1/realtime/sessions
REALTIME_PROVIDER_TOKEN=replace-with-a-gateway-token
DECART_API_KEY=replace-with-a-decart-key
```

Until the gateway is deployed, keep `REALTIME_PROVIDER=mock` for DevTools. The
static FASHN path is independent and remains usable.
