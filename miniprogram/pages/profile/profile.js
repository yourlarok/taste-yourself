// 我的 — 用量、尺寸画像、隐私与数据删除。
const api = require('../../services/api.js');
const format = require('../../utils/format.js');

const app = getApp();

Page({
  data: {
    layout: null,
    status: 'loading',            // loading | ready | error
    errorTitle: '',
    errorDesc: '',
    sessionReady: true,
    usage: null,                  // { static_used, static_limit, realtime_used, realtime_limit }
    profileExists: false,
    profileLine: '未建立',
    profileCreatedText: '',
    capabilityModeText: '',
    capabilities: [],
    privacyOpen: false,
    deleting: false
  },

  onLoad() {
    this.setData({ layout: app.globalData.layout });
  },

  onShow() {
    this.setData({ sessionReady: app.globalData.sessionReady });
    this.load();
  },

  load() {
    this.setData({ status: 'loading' });
    Promise.all([
      api.getUsageInfo(),
      api.getCapabilities(),
      api.getFitProfile().catch((err) => {
        if (err && err.status === 404) return null;
        throw err;
      })
    ]).then((results) => {
      const usage = results[0];
      const capabilitySnapshot = results[1];
      const profile = results[2];
      const stateText = {
        ready: '真实可用',
        configured: '已配置待验收',
        demo: '演示模式',
        partial: '部分可用',
        unavailable: '尚未配置'
      };
      this.setData({
        status: 'ready',
        usage,
        profileExists: !!profile,
        profileLine: profile ? '已建立' : '未建立',
        profileCreatedText: profile
          ? '建立于 ' + format.relativeTime(profile.created_at) + ' · 原始扫描帧已删除'
          : '比较尺码时可在镜前的“尺码差异”中创建',
        capabilityModeText: capabilitySnapshot.mode === 'live'
          ? '当前环境已连接真实服务'
          : capabilitySnapshot.mode === 'mixed'
            ? '当前环境部分能力尚待接通'
            : '当前为演示环境，不代表真实能力已开通',
        capabilities: (capabilitySnapshot.items || []).map((item) => ({
          key: item.key,
          label: item.label,
          state: item.state,
          stateText: stateText[item.state] || item.state,
          notice: item.notice
        }))
      });
    }).catch((err) => {
      const info = api.explainError(err, 'profile');
      this.setData({ status: 'error', errorTitle: info.title, errorDesc: info.desc });
    });
  },

  onRetry() {
    this.load();
  },

  onRetryLogin() {
    app.ensureLogin()
      .then(() => {
        this.setData({ sessionReady: true });
        this.load();
      })
      .catch(() => {
        wx.showToast({ title: '仍然失败，请稍后再试', icon: 'none' });
      });
  },

  onClearProfile() {
    wx.showModal({
      title: '清除尺寸画像？',
      content: '将删除你的身体尺寸数据（原始扫描帧在提取成功后已删除）。清除后可以重新建立。',
      confirmText: '清除画像',
      cancelText: '保留',
      success: (res) => {
        if (!res.confirm) return;
        api.deleteFitProfile()
          .then(() => {
            wx.showToast({ title: '已清除', icon: 'success' });
            this.load();
          })
          .catch((err) => this.showError(err));
      }
    });
  },

  onTogglePrivacy() {
    this.setData({ privacyOpen: !this.data.privacyOpen });
  },

  onDeleteAll() {
    wx.showModal({
      title: '删除全部数据？',
      content: '将删除：我的衣橱、全部试穿记录、尺寸画像与今日用量。此操作无法恢复。',
      confirmText: '继续',
      cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;
        wx.showModal({
          title: '请再次确认',
          content: '删除后无法恢复，确定删除全部数据？',
          confirmText: '删除全部数据',
          confirmColor: '#A8543F',
          cancelText: '取消',
          success: (r) => {
            if (r.confirm) this.doDeleteAll();
          }
        });
      }
    });
  },

  doDeleteAll() {
    this.setData({ deleting: true });
    api.deleteAllData()
      .then(() => {
        this.setData({ deleting: false });
        wx.showToast({ title: '已全部删除', icon: 'success' });
        this.load();
      })
      .catch((err) => {
        this.setData({ deleting: false });
        this.showError(err);
      });
  },

  showError(err) {
    const info = api.explainError(err, 'profile');
    wx.showModal({
      title: info.title,
      content: info.desc,
      showCancel: false,
      confirmText: '知道了'
    });
  },

  onBack() {
    wx.navigateBack({ fail: () => wx.reLaunch({ url: '/pages/home/home' }) });
  }
});
