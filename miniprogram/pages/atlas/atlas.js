const api = require('../../services/api.js');
const app = getApp();
const IMAGES = {
  'wellbeing-sun-orange': '/assets/cats/wellbeing-sun-orange.webp',
  'wellbeing-mist-cloud': '/assets/cats/wellbeing-mist-cloud.webp',
  'wellbeing-moss-tabby': '/assets/cats/wellbeing-moss-tabby.webp',
  'wellbeing-moon-tuxedo': '/assets/cats/wellbeing-moon-tuxedo.webp',
  'wellbeing-night-guardian': '/assets/cats/wellbeing-night-guardian.webp'
};

Page({
  data: { layout: null, loading: true, cards: [], errorText: '' },
  onLoad() { this.setData({ layout: app.globalData.layout }); },
  onShow() {
    app.ensureLogin().then(() => api.listCatCards()).then((cards) => {
      this.setData({ loading: false, cards: cards.map((card) => Object.assign({}, card, { image: IMAGES[card.image_key] || '' })) });
    }).catch((error) => this.setData({ loading: false, errorText: api.explainError(error, 'atlas').desc }));
  },
  onOpenMirror() { wx.switchTab({ url: '/pages/home/home' }); }
});
