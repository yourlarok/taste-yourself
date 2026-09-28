# Embedded realtime try-on

The dynamic fitting-room path is a live WebRTC session; it does not record a
clip, submit a queue job, or fall back to a generated video. The Mini Program
opens a same-origin WebView page with a matching mirror design. That page gets
camera media and the transformed remote stream through Decart's JavaScript SDK.

## Security and flow

1. The Mini Program requires explicit one-time consent before sending camera
   media to Decart.
2. The authenticated API verifies ownership of the active fitting session and
   mints a short-lived Decart client token scoped to `lucy-vton-latest`, the
   configured WebView origin, and a maximum session duration.
3. Only the ephemeral token and selected garment metadata are sent in the URL
   fragment. The permanent Decart key remains server-side; the WebView removes
   the fragment from browser history immediately after parsing it.
4. The WebView connects the front camera to Decart over WebRTC and shows only
   the transformed remote stream. A failed or disconnected session shows an
   error; the raw camera and prerecorded video are never used as substitutes.
5. Selecting another garment updates the existing realtime session. Leaving
   the page or backgrounding the app disconnects and stops camera tracks.

## Production configuration

```dotenv
REALTIME_PROVIDER=decart-realtime
DECART_API_KEY=<server-side Decart key with realtime Lucy VTON access>
REALTIME_WEB_ORIGIN=https://tryon.xuefeitryon.com
```

Builds must run from the repository root through `compose.production.yml` so
the Docker image can build `realtime-web` and copy its static output into the
FastAPI image. Add the same HTTPS host as a WeChat Mini Program business domain
for `web-view`; it must also be allowed for API requests and uploads.

The Mini Program's WebView camera permission and WebRTC compatibility must be
tested on physical iOS and Android WeChat clients. DevTools is not evidence of
live camera compatibility. Until those tests pass, the capability must remain
reported unavailable rather than being presented as a working realtime demo.

## Provider reference

- [Decart realtime virtual try-on example](https://github.com/DecartAI/tryon-examples)
- [Decart JavaScript SDK](https://github.com/DecartAI/sdk)
- [Decart client-token security guidance](https://docs.platform.decart.ai/getting-started/client-tokens)
