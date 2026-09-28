const api = require('../../services/api.js');
const app = getApp();
const SCALE = [0, 25, 50, 75, 100];
const CAT_IMAGES = {
  'wellbeing-sun-orange': '/assets/cats/wellbeing-sun-orange.webp',
  'wellbeing-mist-cloud': '/assets/cats/wellbeing-mist-cloud.webp',
  'wellbeing-moss-tabby': '/assets/cats/wellbeing-moss-tabby.webp',
  'wellbeing-moon-tuxedo': '/assets/cats/wellbeing-moon-tuxedo.webp',
  'wellbeing-night-guardian': '/assets/cats/wellbeing-night-guardian.webp'
};

Page({
  data: {
    layout: null, phase: 'intro', questions: [], step: 0, answers: [], scale: SCALE,
    cameraAvailable: true, submitting: false, result: null, dimensions: [], errorText: ''
  },
  onLoad() {
    this.setData({ layout: app.globalData.layout });
    app.ensureLogin().then(() => Promise.all([api.getMirrorBootstrap(), api.getFunFaceQuestions()]))
      .then(([bootstrap, questions]) => {
        this.setData({ questions, phase: bootstrap.face_test_available_today ? 'intro' : 'used' });
      })
      .catch((error) => this.setData({ errorText: api.explainError(error, 'face').desc }));
  },
  onBack() { wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/home/home' }) }); },
  onStart() { if (this.data.questions.length === 3) this.setData({ phase: 'questions' }); },
  onAnswer(e) {
    const answers = this.data.answers.concat([Number(e.currentTarget.dataset.value)]);
    if (this.data.step === 2) this.setData({ answers, phase: 'camera' });
    else this.setData({ answers, step: this.data.step + 1 });
  },
  onCameraError() {
    this.setData({ cameraAvailable: false, errorText: '无法使用相机，请在真机设置中开启权限。' });
  },
  onCapture() {
    if (!this.data.cameraAvailable || this.data.submitting) return;
    this.setData({ submitting: true, errorText: '' });
    wx.createCameraContext().takePhoto({
      quality: 'high',
      success: (photo) => {
        this.setData({ phase: 'processing' });
        api.submitFunFace(photo.tempImagePath, this.data.answers).then((result) => {
          result.card.image = CAT_IMAGES[result.card.image_key];
          const dimensions = Object.keys(result.dimensions).map((name) => ({
            name, value: result.dimensions[name]
          }));
          this.setData({ result, dimensions, phase: 'result', submitting: false });
        }).catch((error) => {
          const info = api.explainError(error, 'face');
          this.setData({ phase: 'camera', submitting: false, errorText: info.desc || info.title });
        });
      },
      fail: () => this.setData({ submitting: false, errorText: '拍摄没有完成，请重试。' })
    });
  },
  onFinish() { wx.switchTab({ url: '/pages/home/home' }); }
});
