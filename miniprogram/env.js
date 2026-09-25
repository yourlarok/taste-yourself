// env.js — 前端运行配置（唯一需要按环境修改的文件）
//
// useMock = true  ：本地演示模式，所有接口走 services/mock.js，无需后端即可体验完整流程。
// useMock = false ：真实联调模式，所有请求发往 baseUrl，并自动完成微信/开发者工具登录。
//
// mockScenario 仅在演示模式生效，用于逐项验收“完整状态设计”：
//   normal           正常流程（默认）
//   offline          全部接口网络失败 —— 验收“后端不可用 / 网络失败”态
//   quota            静态试穿与动态试衣返回 429 —— 验收“达到每日限额”态
//   server_busy      静态试穿与动态试衣返回 503 —— 验收“Provider 暂不可用”态
//   upload_rejected  上传衣服返回 422 —— 验收“内容审核拒绝”态
//   scan_retake      扫描完成首次返回 422 —— 验收“需要补拍具体角度”态
module.exports = {
  useMock: true,
  baseUrl: 'http://127.0.0.1:8000',
  mockScenario: 'normal',
  mockLatency: 500
};
