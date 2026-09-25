// scan-guide — 尺寸画像采集全屏引导。
// 状态机（由页面驱动）：consent | front | side | uploading | processing | needs_retake | completed | failed
// 一次只显示一个动作；轮廓 + 中文语音 + 震动 + 倒计时引导；切后台自动中止。
const AUDIO = {
  front: '/assets/audio/scan-front.mp3',
  side: '/assets/audio/scan-side.mp3',
  processing: '/assets/audio/scan-processing.mp3',
  needs_retake: '/assets/audio/scan-retake.mp3'
};

Component({
  properties: {
    visible: { type: Boolean, value: false },
    state: { type: String, value: 'consent' },
    retakeSide: { type: String, value: 'side' },   // 需要补拍的角度：front | side
    failTitle: { type: String, value: '扫描未完成' },
    failDesc: { type: String, value: '' },
    processingStep: { type: Number, value: 0 }     // 0 上传 1 检查画面 2 计算尺寸 3 完成
  },

  data: {
    countdown: -1,        // -1 表示未在倒计时
    cameraOk: true,
    steps: ['上传画面', '检查画面', '计算尺寸', '完成'],
    stepIndex: 0,
    capturing: false
  },

  observers: {
    'visible, state': function (visible, state) {
      if (!visible) {
        this.teardown();
        return;
      }
      if (state === 'front' || state === 'side') {
        this.startCaptureCountdown(state);
      } else {
        this.clearCountdown();
        if (state === 'processing' || state === 'needs_retake') {
          this.playVoice(state);
        }
      }
    },
    processingStep(i) {
      this.setData({ stepIndex: i });
    }
  },

  lifetimes: {
    detached() {
      this.teardown();
    }
  },

  pageLifetimes: {
    hide() {
      // 页面切后台：停止语音与倒计时，并通知页面终止扫描
      this.teardown();
      if (this.data.visible) this.triggerEvent('background');
    }
  },

  methods: {
    /* ---- 倒计时采集 ---- */
    startCaptureCountdown(side) {
      this.clearCountdown();
      this.setData({ countdown: 3, capturing: false });
      this.playVoice(side);
      this.vibrate('light');
      let n = 3;
      this._timer = setInterval(() => {
        n -= 1;
        if (n > 0) {
          this.setData({ countdown: n });
          this.vibrate('light');
        } else {
          this.clearCountdown();
          this.setData({ capturing: true });
          this.vibrate('medium');
          this.triggerEvent('captured', { side });
        }
      }, 1000);
    },

    clearCountdown() {
      if (this._timer) {
        clearInterval(this._timer);
        this._timer = null;
      }
      if (this.data.countdown !== -1 || this.data.capturing) {
        this.setData({ countdown: -1, capturing: false });
      }
    },

    /* ---- 语音与震动 ---- */
    playVoice(key) {
      this.stopVoice();
      const src = AUDIO[key];
      if (!src) return;
      const ctx = wx.createInnerAudioContext();
      ctx.src = src;
      ctx.onEnded(() => { ctx.destroy(); });
      ctx.onError(() => { ctx.destroy(); });
      ctx.play();
      this._audio = ctx;
    },

    stopVoice() {
      if (this._audio) {
        try { this._audio.stop(); this._audio.destroy(); } catch (e) { /* ignore */ }
        this._audio = null;
      }
    },

    vibrate(type) {
      if (wx.vibrateShort) {
        wx.vibrateShort({ type: type === 'medium' ? 'medium' : 'light', fail: () => {} });
      }
    },

    teardown() {
      this.clearCountdown();
      this.stopVoice();
    },

    /* ---- 真实模式取景 ---- */
    onCameraError() {
      this.setData({ cameraOk: false });
      this.triggerEvent('cameraerror');
    },

    takePhoto() {
      return new Promise((resolve, reject) => {
        if (!this.data.cameraOk) {
          reject(new Error('camera unavailable'));
          return;
        }
        const ctx = wx.createCameraContext(this);
        ctx.takePhoto({
          quality: 'high',
          success: (res) => resolve(res.tempImagePath),
          fail: reject
        });
      });
    },

    /* ---- 交互事件 ---- */
    onAgree() { this.triggerEvent('agree'); },
    onCancel() { this.stopVoice(); this.triggerEvent('cancel'); },
    onRetake() { this.triggerEvent('retake', { side: this.data.retakeSide }); },
    onRetry() { this.triggerEvent('retry'); },
    onFinish() { this.triggerEvent('finish'); },
    noop() {}
  }
});
