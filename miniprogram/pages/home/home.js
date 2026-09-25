// 首页 — 试衣准备空间。
// 状态机：loading | empty | ready | error
// 结构：顶部（避让胶囊）→ 主舞台（全区域可点）→ 上下文内容带 → 唯一主动作。
const api = require('../../services/api.js');
const format = require('../../utils/format.js');

const app = getApp();

Page({
  data: {
    layout: null,
    status: 'loading',
    errorTitle: '',
    errorDesc: '',
    recent: null,              // { garmentName, updatedText, resultImage }
    lastTryonText: '还没有试穿记录',
    wardrobeThumbs: [],
    wardrobeCount: 0,
    profileLine: '',
    ctaText: '进入镜前',
    demoGarment: { name: '', image: '' }
  },

  onLoad() {
    this.setData({ layout: app.globalData.layout });
  },

  onShow() {
    this.load();
  },

  // 404 视为空态而非错误
  tolerate404(promise, fallback) {
    return promise.catch((err) => {
      if (err && err.status === 404) return fallback;
      throw err;
    });
  },

  load() {
    this.setData({ status: 'loading' });
    Promise.all([
      this.tolerate404(api.getRecentExperience(), null),
      this.tolerate404(api.listWardrobeGarments(), { garments: [] }),
      this.tolerate404(api.getFitProfile(), null),
      this.tolerate404(api.listCatalogGarments(), { garments: [] })
    ]).then((results) => {
      const recent = results[0];
      const wardrobe = results[1].garments || [];
      const profile = results[2];
      const catalog = results[3].garments || [];
      const demo = catalog[0] || {};

      const next = {
        wardrobeThumbs: wardrobe.slice(0, 3).map((g) => ({ id: g.id, image: g.image_url })),
        wardrobeCount: wardrobe.length,
        profileLine: profile ? '尺寸画像已建立 · 可查看尺码差异' : '需要比较尺码时再建立，不影响试穿',
        demoGarment: { name: demo.name || '示例衣服', image: demo.image_url || '' }
      };

      if (recent) {
        const timeText = format.relativeTime(recent.updated_at);
        next.status = 'ready';
        next.recent = {
          garmentName: recent.garment_name,
          updatedText: timeText,
          resultImage: recent.result_image
        };
        next.lastTryonText = recent.garment_name + ' · ' + timeText;
        next.ctaText = '进入镜前';
      } else {
        next.status = 'empty';
        next.recent = null;
        next.lastTryonText = '还没有试穿记录';
        next.ctaText = '开始第一次试穿';
      }
      this.setData(next);
    }).catch((err) => {
      const info = api.explainError(err, 'home');
      this.setData({ status: 'error', errorTitle: info.title, errorDesc: info.desc });
    });
  },

  enterStudio() {
    wx.navigateTo({ url: '/pages/studio/studio' });
  },

  // 主舞台“更换衣服”：进入镜前并聚焦衣服轨道
  onStageChange() {
    wx.navigateTo({ url: '/pages/studio/studio' });
  },

  onAddGarment() {
    wx.navigateTo({ url: '/pages/studio/studio?add=1' });
  },

  goProfile() {
    wx.navigateTo({ url: '/pages/profile/profile' });
  },

  onRetry() {
    this.load();
  }
});
