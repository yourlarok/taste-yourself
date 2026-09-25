// app.js — 全局入口：布局度量、静默登录、全局标记
const api = require('./services/api.js');

App({
  globalData: {
    layout: null,
    reduceMotion: false,
    sessionReady: false
  },

  onLaunch() {
    this.globalData.layout = measureLayout();
    this.globalData.reduceMotion = !!this.globalData.layout.reduceMotion;
    // 静默登录：失败不阻塞首页渲染，页面会展示可重试状态
    api.login().then(() => {
      this.globalData.sessionReady = true;
    }).catch(() => {
      this.globalData.sessionReady = false;
    });
  },

  ensureLogin() {
    return api.login().then(() => {
      this.globalData.sessionReady = true;
    });
  }
});

// 自定义导航栏布局度量：状态栏、胶囊、底部安全区一次算好，供所有页面使用
function measureLayout() {
  const win = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
  const statusBarHeight = win.statusBarHeight || 20;

  let capsule = null;
  try {
    const rect = wx.getMenuButtonBoundingClientRect();
    if (rect && rect.width) capsule = rect;
  } catch (e) { /* ignore */ }
  if (!capsule) {
    const w = win.windowWidth || 375;
    capsule = {
      top: statusBarHeight + 6,
      bottom: statusBarHeight + 38,
      left: w - 95,
      right: w - 8,
      width: 87,
      height: 32
    };
  }

  const navContentHeight = (capsule.top - statusBarHeight) * 2 + capsule.height;
  const safeBottom = win.safeArea ? Math.max(0, win.windowHeight - win.safeArea.bottom) : 0;

  return {
    statusBarHeight,
    navContentHeight,
    navBarHeight: statusBarHeight + navContentHeight,
    windowWidth: win.windowWidth || 375,
    windowHeight: win.windowHeight || 667,
    safeBottom,
    // “我的”等右上角入口的右侧留白，保证不与微信胶囊重叠
    capsuleRightGap: (win.windowWidth || 375) - capsule.left + 8,
    reduceMotion: !!win.reduceMotionEnabled
  };
}
