const api = require('../../services/api.js');

Page({
  data: { src: '', error: '' },

  onLoad() {
    const bootstrap = wx.getStorageSync('ty_live_bootstrap');
    wx.removeStorageSync('ty_live_bootstrap');
    if (!bootstrap || !bootstrap.sessionId) {
      this.setData({ error: '试衣会话已失效，请返回后重新进入。' });
      return;
    }
    this._bootstrap = bootstrap;
    api.createRealtimeClientToken(bootstrap.sessionId).then((token) => {
      if (!token || !token.apiKey) throw new api.ApiError(503, '实时试衣服务暂不可用', 'REALTIME_UNAVAILABLE');
      const payload = Object.assign({}, bootstrap, { apiKey: token.apiKey });
      const src = api.absoluteMediaUrl('/live-mirror/index.html') + '#d=' + encodeURIComponent(JSON.stringify(payload));
      this.setData({ src });
    }).catch((error) => {
      const info = api.explainError(error, 'realtime');
      this.setData({ error: info.title + '：' + info.desc });
    });
  },

  onWebviewMessage(event) {
    const messages = event && event.detail && event.detail.data;
    const value = Array.isArray(messages) ? messages[messages.length - 1] : messages;
    if (value && value.selectedGarmentId) this._selectedGarmentId = value.selectedGarmentId;
  },

  onWebviewError() {
    this.setData({ src: '', error: '实时试衣页面无法载入，请检查网络后重试。' });
  },

  onUnload() {
    if (this._selectedGarmentId) {
      wx.setStorageSync('ty_live_selected_garment', this._selectedGarmentId);
    }
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.reLaunch({ url: '/pages/home/home' }) });
  }
});
