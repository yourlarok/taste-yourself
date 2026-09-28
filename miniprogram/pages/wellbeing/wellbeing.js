const api = require('../../services/api.js');

const app = getApp();
const OPTION_LABELS = ['始终如此', '大部分时间', '超过一半时间', '少于一半时间', '偶尔', '完全没有'];
const OPTION_VALUES = [5, 4, 3, 2, 1, 0];
const CAT_IMAGES = {
  'wellbeing-sun-orange': '/assets/cats/wellbeing-sun-orange.webp',
  'wellbeing-mist-cloud': '/assets/cats/wellbeing-mist-cloud.webp',
  'wellbeing-moss-tabby': '/assets/cats/wellbeing-moss-tabby.webp',
  'wellbeing-moon-tuxedo': '/assets/cats/wellbeing-moon-tuxedo.webp',
  'wellbeing-night-guardian': '/assets/cats/wellbeing-night-guardian.webp'
};

Page({
  data: {
    layout: null,
    phase: 'intro',
    questions: [],
    step: 0,
    answers: [],
    options: OPTION_VALUES.map((value, index) => ({ value, label: OPTION_LABELS[index] })),
    contributors: [
      { key: 'sleep', label: '睡眠与作息', selected: false },
      { key: 'workload', label: '任务与工作量', selected: false },
      { key: 'relationships', label: '关系与沟通', selected: false },
      { key: 'physical', label: '身体不适', selected: false },
      { key: 'uncertainty', label: '持续的不确定感', selected: false },
      { key: 'none', label: '说不清具体原因', selected: false }
    ],
    dangerChoice: '',
    submitting: false,
    result: null,
    errorText: ''
  },

  onLoad() {
    this.setData({ layout: app.globalData.layout });
    app.ensureLogin()
      .then(() => api.getWellbeingQuestions())
      .then((questions) => this.setData({ questions }))
      .catch((error) => this.setData({ errorText: api.explainError(error, 'wellbeing').desc }));
  },

  onBack() { wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/home/home' }) }); },
  onStart() { if (this.data.questions.length === 5) this.setData({ phase: 'questions' }); },

  onAnswer(e) {
    const value = Number(e.currentTarget.dataset.value);
    const answers = this.data.answers.concat([value]);
    if (this.data.step >= this.data.questions.length - 1) {
      this.setData({ answers, phase: 'context' });
    } else {
      this.setData({ answers, step: this.data.step + 1 });
    }
  },

  onToggleContributor(e) {
    const key = e.currentTarget.dataset.key;
    const contributors = this.data.contributors.map((item) => {
      if (item.key === key) return Object.assign({}, item, { selected: !item.selected });
      if (key === 'none' || (item.key === 'none' && item.selected)) {
        return Object.assign({}, item, { selected: false });
      }
      return item;
    });
    const chosen = contributors.filter((item) => item.selected);
    if (chosen.length > 3) return;
    this.setData({ contributors });
  },

  onDangerChoice(e) { this.setData({ dangerChoice: e.currentTarget.dataset.value }); },

  onSubmit() {
    if (!this.data.dangerChoice || this.data.submitting) {
      if (!this.data.dangerChoice) wx.showToast({ title: '请先回答安全确认', icon: 'none' });
      return;
    }
    this.setData({ submitting: true, errorText: '' });
    api.submitWellbeing({
      answers: this.data.answers,
      contributors: this.data.contributors.filter((item) => item.selected).map((item) => item.key),
      immediate_danger: this.data.dangerChoice === 'yes'
    }).then((result) => {
      result.card.image = CAT_IMAGES[result.card.image_key];
      this.setData({ result, phase: 'result', submitting: false });
    }).catch((error) => {
      const info = api.explainError(error, 'wellbeing');
      this.setData({ errorText: info.desc || info.title, submitting: false });
    });
  },

  onFinish() { wx.switchTab({ url: '/pages/home/home' }); }
});
