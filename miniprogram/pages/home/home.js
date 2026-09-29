const api = require('../../services/api.js');

const app = getApp();

Page({
  data: {
    layout: null,
    ready: false,
    conversationId: '',
    greeting: '',
    suggestions: [],
    messages: [],
    inputValue: '',
    sending: false,
    recording: false,
    transcribing: false,
    introVisible: true,
    scrollAnchor: '',
    faceAvailable: true,
    errorText: ''
  },

  onLoad() {
    this.setData({ layout: app.globalData.layout });
    this.setupRecorder();
    this.startMirror();
  },

  onUnload() {
    if (this._recorder && this.data.recording) this._recorder.stop();
  },

  setupRecorder() {
    if (!wx.getRecorderManager) return;
    this._recorder = wx.getRecorderManager();
    this._recorder.onStart(() => this.setData({ recording: true, errorText: '' }));
    this._recorder.onStop((result) => {
      this.setData({ recording: false });
      if (!result || !result.tempFilePath) return;
      this.transcribeAndSend(result.tempFilePath);
    });
    this._recorder.onError(() => {
      this.setData({ recording: false, transcribing: false });
      wx.showToast({ title: '没有录到声音，请检查麦克风权限', icon: 'none' });
    });
  },

  onVoiceTap() {
    if (this.data.sending || this.data.transcribing || !this._recorder) return;
    if (this.data.recording) {
      this._recorder.stop();
      return;
    }
    this.setData({ introVisible: false });
    this._recorder.start({
      duration: 15000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 48000,
      format: 'mp3'
    });
  },

  transcribeAndSend(filePath) {
    this.setData({ transcribing: true });
    api.transcribeMirrorAudio(filePath)
      .then((result) => {
        const text = String(result.text || '').trim();
        this.setData({ transcribing: false, inputValue: text });
        if (text) this.send(text);
      })
      .catch((error) => {
        const info = api.explainError(error, 'mirror');
        this.setData({ transcribing: false });
        wx.showToast({ title: info.desc || '没有听清，请再说一次', icon: 'none' });
      });
  },

  startMirror() {
    this.setData({ ready: false, errorText: '' });
    app.ensureLogin()
      .then(() => Promise.all([api.getMirrorBootstrap(), api.createMirrorConversation()]))
      .then(([bootstrap, conversation]) => {
        this.setData({
          ready: true,
          conversationId: conversation.id,
          greeting: bootstrap.greeting,
          suggestions: bootstrap.suggestions || [],
          faceAvailable: bootstrap.face_test_available_today,
          messages: [{ id: 'welcome', role: 'mirror', content: bootstrap.greeting }],
          scrollAnchor: 'message-welcome'
        });
      })
      .catch((error) => {
        const info = api.explainError(error, 'mirror');
        this.setData({ errorText: info.desc || info.title });
      });
  },

  onInput(e) { this.setData({ inputValue: e.detail.value }); },

  onSuggestion(e) {
    const content = e.currentTarget.dataset.text;
    this.setData({ inputValue: content, introVisible: false });
    this.send(content);
  },

  onSend() { this.send(this.data.inputValue); },

  send(rawContent) {
    const content = String(rawContent || '').trim();
    if (!content || this.data.sending || !this.data.conversationId) return;
    const userId = 'user-' + Date.now();
    this.setData({
      messages: this.data.messages.concat([{ id: userId, role: 'user', content }]),
      inputValue: '',
      sending: true,
      introVisible: false,
      scrollAnchor: 'message-' + userId
    });
    api.sendMirrorMessage(this.data.conversationId, content)
      .then((result) => {
        const item = { id: result.message_id, role: 'mirror', content: result.reply };
        this.setData({
          messages: this.data.messages.concat([item]),
          sending: false,
          scrollAnchor: 'message-' + item.id
        });
        this.dispatchAction(result.action || {});
      })
      .catch((error) => {
        const info = api.explainError(error, 'mirror');
        const item = {
          id: 'error-' + Date.now(),
          role: 'system',
          content: info.desc || '魔镜暂时没有听清，请稍后再试。'
        };
        this.setData({
          messages: this.data.messages.concat([item]),
          sending: false,
          scrollAnchor: 'message-' + item.id
        });
      });
  },

  dispatchAction(action) {
    const type = action.type;
    const payload = action.payload || {};
    if (type === 'start_wellbeing') {
      wx.navigateTo({ url: '/pages/wellbeing/wellbeing' });
    } else if (type === 'open_tryon' || type === 'show_garments') {
      wx.setStorageSync('cat_mirror_selected_garments', payload.garment_ids || []);
      if (payload.scene) wx.setStorageSync('cat_mirror_scene', payload.scene);
      wx.switchTab({ url: '/pages/studio/studio' });
    } else if (type === 'open_wardrobe') {
      wx.switchTab({ url: '/pages/studio/studio' });
    } else if (type === 'open_atlas') {
      wx.switchTab({ url: '/pages/atlas/atlas' });
    } else if (type === 'start_fun_face') {
      if (this.data.faceAvailable) wx.navigateTo({ url: '/pages/fun-face/fun-face' });
      else wx.showToast({ title: '今天已经照过啦', icon: 'none' });
    }
  },

  onDismissIntro() { this.setData({ introVisible: false }); },
  onOpenWellbeing() { wx.navigateTo({ url: '/pages/wellbeing/wellbeing' }); },
  onOpenTryon() { wx.switchTab({ url: '/pages/studio/studio' }); },
  onOpenAtlas() { wx.switchTab({ url: '/pages/atlas/atlas' }); }
});
