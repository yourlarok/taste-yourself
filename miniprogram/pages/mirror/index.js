const api = require("../../services/api");

const FALLBACK_GARMENTS = [
  { id: "knit-sand", name: "米色针织上衣", tone: "sand", fitDataAvailable: true },
  { id: "denim-blue", name: "深蓝牛仔夹克", tone: "blue", fitDataAvailable: true },
  { id: "coat-brown", name: "棕色短外套", tone: "brown", fitDataAvailable: true }
];

const FALLBACK_SIZES = [
  {
    label: "M",
    detail: "胸部余量 2 cm",
    note: "低于参考区间，视觉上可能更贴身"
  },
  {
    label: "L",
    detail: "胸部余量 8 cm",
    note: "位于当前参考区间"
  },
  {
    label: "XL",
    detail: "胸部余量 16 cm",
    note: "高于参考区间，视觉上可能更宽松"
  }
];

const SCAN_STEPS = [
  { angle: "front", instruction: "面向镜头，双臂自然分开" },
  { angle: "side", instruction: "向左转身，保持侧面站立" }
];

Page({
  data: {
    inStudio: false,
    sessionId: "",
    backendConnected: false,
    cameraAvailable: true,
    cameraMessage: "",
    resultImageUrl: "",
    resultNotice: "",
    recentPersonImageId: "",
    activeGarment: 0,
    modeLabel: "静态试穿已就绪",
    sheet: "none",
    hasFitProfile: false,
    liveRemaining: 0,
    liveStreamActive: false,
    livePublishUrl: "",
    livePlayUrl: "",
    scanActive: false,
    scanCountdown: 0,
    scanInstruction: "",
    scanProgress: "",
    usageSummary: "正在读取今日用量…",
    recentGarmentName: "还没有试穿记录",
    recentTimeLabel: "从一件衣服开始",
    recentImageUrl: "",
    garments: FALLBACK_GARMENTS,
    sizeAnalysis: FALLBACK_SIZES
  },

  onLoad() {
    this.setData({ hasFitProfile: Boolean(wx.getStorageSync("fitProfileVersion")) });
    this.loadCatalog();
    this.syncFitProfile();
    this.loadRecentExperience();
  },

  onUnload() {
    this.stopLiveSession();
    this.stopScanTimer();
    this.stopScanVoice();
  },

  onHide() {
    this.stopLiveSession();
    if (this.data.scanActive) this.cancelBodyScan();
  },

  async loadCatalog() {
    try {
      const [catalog, wardrobe] = await Promise.all([
        api.listGarments(),
        api.listWardrobe()
      ]);
      const garments = catalog
        .map((item) => ({
          ...item,
          imageUrl: api.resultUrl(item.image_url),
          fitDataAvailable: true
        }))
        .concat(wardrobe.map((item) => ({
          id: item.id,
          name: item.name,
          tone: "custom",
          imageUrl: api.resultUrl(item.image_url),
          fitDataAvailable: false
        })));
      this.setData({
        garments,
        backendConnected: true
      });
    } catch (error) {
      this.setData({ backendConnected: false, garments: FALLBACK_GARMENTS });
    }
  },

  async syncFitProfile() {
    try {
      const profile = await api.getMyFitProfile();
      wx.setStorageSync("fitProfileVersion", profile.source_scan_id);
      this.setData({ hasFitProfile: true });
    } catch (error) {
      if (error.statusCode === 404) {
        wx.removeStorageSync("fitProfileVersion");
        this.setData({ hasFitProfile: false });
      }
    }
  },

  async loadRecentExperience() {
    try {
      const recent = await api.getRecentExperience();
      const updatedAt = new Date(recent.updated_at);
      this.setData({
        recentGarmentName: recent.garment_name,
        recentTimeLabel: `${updatedAt.getMonth() + 1}月${updatedAt.getDate()}日 ${String(updatedAt.getHours()).padStart(2, "0")}:${String(updatedAt.getMinutes()).padStart(2, "0")}`,
        recentImageUrl: recent.result_url ? api.resultUrl(recent.result_url) : ""
      });
    } catch (error) {
      if (error.statusCode !== 404) this.setData({ backendConnected: false });
    }
  },

  async enterStudio() {
    this.setData({ inStudio: true, modeLabel: "正在准备镜前体验…" });
    const garment = this.data.garments[this.data.activeGarment];
    try {
      const session = await api.createExperience(garment.id);
      this.setData({
        sessionId: session.id,
        backendConnected: true,
        modeLabel: "选择衣服后，定格一张本人画面"
      });
    } catch (error) {
      this.setData({
        backendConnected: false,
        modeLabel: "本地演示 · 未连接后端"
      });
    }
  },

  leaveStudio() {
    this.stopLiveSession();
    this.setData({
      inStudio: false,
      sheet: "none",
      liveRemaining: 0,
      modeLabel: "静态试穿已就绪"
    });
  },

  handleCameraError(event) {
    this.setData({
      cameraAvailable: false,
      cameraMessage: event.detail && event.detail.errMsg
        ? "相机暂不可用，可稍后重试"
        : "相机暂不可用"
    });
  },

  async chooseGarment(event) {
    const index = Number(event.currentTarget.dataset.index);
    this.setData({ activeGarment: index, modeLabel: "正在更新静态试穿…" });
    if (!this.data.sessionId) {
      this.setData({ modeLabel: "本地演示 · 未连接后端" });
      return;
    }
    try {
      const garment = this.data.garments[index];
      await api.selectGarment(this.data.sessionId, garment.id);
      if (this.data.recentPersonImageId) {
        await this.refreshStaticTryOn(this.data.recentPersonImageId);
      } else {
        this.setData({ modeLabel: "衣服已切换 · 点击定格试穿" });
      }
    } catch (error) {
      this.setData({ backendConnected: false, modeLabel: "更新失败，仍保留当前画面" });
    }
  },

  async refreshStaticTryOn(personImageId = null) {
    const result = await api.generateStatic(this.data.sessionId, personImageId);
    this.setData({
      backendConnected: true,
      resultImageUrl: result.result_url ? api.resultUrl(result.result_url) : this.data.resultImageUrl,
      resultNotice: result.result_url ? result.notice : "",
      modeLabel: result.status === "failed"
        ? result.notice
        : result.provider === "mock" ? "静态试穿已就绪 · 模拟" : "静态试穿已就绪"
    });
  },

  captureStaticTryOn() {
    if (!this.data.sessionId || !this.data.cameraAvailable) {
      wx.showToast({ title: "相机或体验会话尚未就绪", icon: "none" });
      return;
    }
    this.setData({ modeLabel: "正在定格本人画面…" });
    const camera = wx.createCameraContext();
    camera.takePhoto({
      quality: "high",
      success: async (photo) => {
        try {
          const uploaded = await api.uploadPersonImage(photo.tempImagePath);
          this.setData({
            modeLabel: "正在生成静态试穿…",
            recentPersonImageId: uploaded.id
          });
          await this.refreshStaticTryOn(uploaded.id);
        } catch (error) {
          this.setData({ modeLabel: "静态试穿生成失败" });
          wx.showToast({ title: "请检查后端或图片", icon: "none" });
        }
      },
      fail: () => {
        this.setData({ modeLabel: "未能取得相机画面" });
      }
    });
  },

  clearResultImage() {
    this.setData({ resultImageUrl: "", resultNotice: "", modeLabel: "已回到镜头" });
  },

  saveResultImage() {
    if (!this.data.resultImageUrl) {
      wx.showToast({ title: "请先完成一次静态试穿", icon: "none" });
      return;
    }
    wx.downloadFile({
      url: this.data.resultImageUrl,
      success: ({ statusCode, tempFilePath }) => {
        if (statusCode !== 200) {
          wx.showToast({ title: "结果下载失败", icon: "none" });
          return;
        }
        wx.saveImageToPhotosAlbum({
          filePath: tempFilePath,
          success: () => wx.showToast({ title: "已保存到相册", icon: "success" }),
          fail: () => wx.showToast({ title: "未获得相册保存权限", icon: "none" })
        });
      },
      fail: () => wx.showToast({ title: "结果下载失败", icon: "none" })
    });
  },

  async openFitAnalysis() {
    const garment = this.data.garments[this.data.activeGarment];
    if (!garment.fitDataAvailable) {
      this.setData({ sheet: "product-data-missing" });
      return;
    }
    if (!this.data.hasFitProfile) {
      this.setData({ sheet: "scan" });
      return;
    }

    try {
      const result = await api.getFitAnalysis(garment.id);
      const sizeAnalysis = result.variants.map((variant) => {
        const reason = variant.reasons[0];
        return {
          label: variant.size_label,
          detail: reason ? `胸部余量 ${reason.ease_cm} cm` : "缺少测量数据",
          note: variant.summary
        };
      });
      this.setData({ sizeAnalysis, sheet: "analysis", backendConnected: true });
    } catch (error) {
      if (error.statusCode === 404 || error.statusCode === 409) {
        wx.removeStorageSync("fitProfileVersion");
        this.setData({ hasFitProfile: false, sheet: "scan" });
        return;
      }
      this.setData({ backendConnected: false, sheet: "none", modeLabel: "尺码数据读取失败" });
      wx.showToast({ title: "尺码数据暂时不可用", icon: "none" });
    }
  },

  closeSheet() {
    this.setData({ sheet: "none" });
  },

  async openAccountSheet() {
    this.setData({ sheet: "account" });
    try {
      const usage = await api.getMyUsage();
      this.setData({
        usageSummary: `今日静态 ${usage.static.used}/${usage.static.limit} · 动态 ${usage.realtime.used}/${usage.realtime.limit}`
      });
    } catch (error) {
      this.setData({ usageSummary: "今日用量暂时无法读取" });
    }
  },

  openPrivacyContract() {
    wx.openPrivacyContract({
      fail: () => wx.showToast({ title: "请在小程序后台配置隐私指引", icon: "none" })
    });
  },

  async clearFitProfile() {
    try {
      await api.deleteFitProfile();
      wx.removeStorageSync("fitProfileVersion");
      this.setData({ hasFitProfile: false, sheet: "none" });
      wx.showToast({ title: "尺寸画像已清除", icon: "success" });
    } catch (error) {
      wx.showToast({ title: "清除失败，请稍后重试", icon: "none" });
    }
  },

  deleteAllData() {
    wx.showModal({
      title: "删除全部数据？",
      content: "衣橱、人像、扫描帧和试穿记录都会删除，且无法恢复。",
      confirmText: "确认删除",
      confirmColor: "#8a3328",
      success: async ({ confirm }) => {
        if (!confirm) return;
        try {
          await api.deleteMyData();
          wx.clearStorageSync();
          this.setData({
            garments: FALLBACK_GARMENTS,
            activeGarment: 0,
            hasFitProfile: false,
            sessionId: "",
            resultImageUrl: "",
            resultNotice: "",
            recentPersonImageId: "",
            sheet: "none",
            inStudio: false
          });
          wx.showToast({ title: "数据已删除", icon: "success" });
        } catch (error) {
          wx.showToast({ title: "删除失败，请稍后重试", icon: "none" });
        }
      }
    });
  },

  async startBodyScan() {
    if (!this.data.sessionId) {
      wx.showToast({ title: "请先进入镜前", icon: "none" });
      return;
    }
    this.setData({ sheet: "none", modeLabel: "正在准备扫描…" });
    try {
      const scan = await api.createBodyScan(this.data.sessionId);
      this.scanId = scan.id;
      this.setData({ scanActive: true });
      this.runScanStep(0);
    } catch (error) {
      this.setData({ modeLabel: "尺寸画像建立失败" });
      wx.showToast({ title: "请稍后重试", icon: "none" });
    }
  },

  runScanStep(index) {
    if (index >= SCAN_STEPS.length) {
      this.finishBodyScan();
      return;
    }
    this.scanStepIndex = index;
    const step = SCAN_STEPS[index];
    this.setData({
      scanInstruction: step.instruction,
      scanProgress: `${index + 1} / ${SCAN_STEPS.length}`,
      scanCountdown: 3,
      modeLabel: "请跟随画面完成扫描"
    });
    this.playScanVoice(step.angle);
    wx.vibrateShort({ type: "light" });
    this.stopScanTimer();
    this.scanTimer = setInterval(() => {
      const next = this.data.scanCountdown - 1;
      this.setData({ scanCountdown: next });
      if (next <= 0) {
        this.stopScanTimer();
        this.captureScanFrame(step, index);
      } else {
        wx.vibrateShort({ type: "light" });
      }
    }, 1000);
  },

  captureScanFrame(step, index) {
    const camera = wx.createCameraContext();
    camera.takePhoto({
      quality: "normal",
      success: async (photo) => {
        try {
          await api.uploadBodyScanFrame(this.scanId, step.angle, photo.tempImagePath);
          wx.vibrateShort({ type: "medium" });
          this.runScanStep(index + 1);
        } catch (error) {
          this.failBodyScan("画面上传失败，请重新开始");
        }
      },
      fail: () => this.failBodyScan("未能取得相机画面，请重新开始")
    });
  },

  async finishBodyScan() {
    this.setData({ scanInstruction: "后台正在检查画面…", scanCountdown: 0 });
    try {
      const result = await api.completeBodyScan(this.scanId);
      if (result.status === "needs_retake") {
        this.failBodyScan("有角度需要补拍，请重新开始");
        return;
      }
      if (result.status !== "completed") {
        this.failBodyScan(result.notice || "尺寸画像建立失败");
        return;
      }
      this.setData({
        scanActive: false,
        hasFitProfile: result.status === "completed",
        modeLabel: result.provider === "mock" ? "测试尺寸画像已就绪 · 模拟" : "尺寸画像已就绪"
      });
      wx.setStorageSync("fitProfileVersion", result.id);
      wx.showToast({ title: "测试画像已建立", icon: "success" });
    } catch (error) {
      this.failBodyScan("后台处理失败，请稍后重试");
    }
  },

  failBodyScan(message) {
    this.stopScanTimer();
    this.stopScanVoice();
    this.setData({ scanActive: false, modeLabel: message });
    wx.showToast({ title: message, icon: "none" });
  },

  cancelBodyScan() {
    this.stopScanTimer();
    this.stopScanVoice();
    this.setData({ scanActive: false, modeLabel: "已取消尺寸扫描" });
  },

  stopScanTimer() {
    if (this.scanTimer) {
      clearInterval(this.scanTimer);
      this.scanTimer = null;
    }
  },

  playScanVoice(angle) {
    this.stopScanVoice();
    const audio = wx.createInnerAudioContext();
    audio.src = angle === "front"
      ? "/assets/scan-front.mp3"
      : "/assets/scan-side.mp3";
    audio.volume = 0.9;
    audio.onEnded(() => {
      audio.destroy();
      if (this.scanVoice === audio) this.scanVoice = null;
    });
    audio.onError(() => {
      audio.destroy();
      if (this.scanVoice === audio) this.scanVoice = null;
    });
    this.scanVoice = audio;
    audio.play();
  },

  stopScanVoice() {
    if (this.scanVoice) {
      this.scanVoice.stop();
      this.scanVoice.destroy();
      this.scanVoice = null;
    }
  },

  skipBodyScan() {
    this.setData({ sheet: "insufficient" });
  },

  async startLiveTryOn() {
    if (this.data.liveRemaining > 0) return;

    if (!this.data.sessionId) {
      wx.showToast({ title: "体验会话尚未就绪", icon: "none" });
      return;
    }

    try {
      const realtime = await api.createRealtime(this.data.sessionId);
      if (realtime.status !== "ready") {
        this.setData({ modeLabel: realtime.notice || "实时试穿暂不可用" });
        wx.showToast({ title: "实时试穿暂不可用", icon: "none" });
        return;
      }
      const hasStreamPair = Boolean(realtime.publish_url && realtime.play_url);
      this.setData({
        backendConnected: true,
        liveRemaining: Math.min(realtime.max_duration_seconds || 15, 15),
        liveStreamActive: hasStreamPair,
        livePublishUrl: realtime.publish_url || "",
        livePlayUrl: realtime.play_url || "",
        modeLabel: realtime.provider === "mock" ? "实时模式 · 模拟" : "实时试衣中"
      }, () => {
        if (hasStreamPair) this.startLiveContexts();
        this.startLiveTimer();
      });
    } catch (error) {
      this.setData({ backendConnected: false, modeLabel: "实时试穿连接失败" });
      wx.showToast({ title: "实时服务连接失败", icon: "none" });
    }
  },

  startLiveContexts() {
    this.livePusherContext = wx.createLivePusherContext("livePusher", this);
    this.livePlayerContext = wx.createLivePlayerContext("livePlayer", this);
    this.livePusherContext.start({
      fail: () => this.handleLiveFailure("未能启动相机推流")
    });
    this.livePlayerContext.play({
      fail: () => this.handleLiveFailure("未能播放实时结果")
    });
  },

  startLiveTimer() {
    this.stopLiveTimer();
    this.liveTimer = setInterval(() => {
      const next = this.data.liveRemaining - 1;
      if (next <= 0) {
        this.stopLiveSession("15 秒体验已结束");
        return;
      }
      this.setData({ liveRemaining: next });
    }, 1000);
  },

  handleLiveState(event) {
    const code = event.detail && event.detail.code;
    if (code && code < 0) this.handleLiveFailure("实时链路已中断");
  },

  handleLiveFailure(message) {
    if (typeof message !== "string") message = "实时链路已中断";
    this.stopLiveSession(message);
    wx.showToast({ title: message, icon: "none" });
  },

  stopLiveSession(modeLabel) {
    this.stopLiveTimer();
    if (this.livePusherContext) this.livePusherContext.stop();
    if (this.livePlayerContext) this.livePlayerContext.stop();
    this.livePusherContext = null;
    this.livePlayerContext = null;
    this.setData({
      liveRemaining: 0,
      liveStreamActive: false,
      livePublishUrl: "",
      livePlayUrl: "",
      ...(modeLabel ? { modeLabel } : {})
    });
  },

  stopLiveTimer() {
    if (this.liveTimer) {
      clearInterval(this.liveTimer);
      this.liveTimer = null;
    }
  },

  addGarment() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      success: async (choice) => {
        const file = choice.tempFiles && choice.tempFiles[0];
        if (!file) return;
        this.setData({ modeLabel: "正在加入衣橱…" });
        try {
          const uploaded = await api.uploadGarment(file.tempFilePath, "新加入的衣服", "tops");
          const custom = {
            id: uploaded.id,
            name: uploaded.name,
            tone: "custom",
            imageUrl: api.resultUrl(uploaded.image_url),
            fitDataAvailable: false
          };
          const garments = this.data.garments.concat(custom);
          const activeGarment = garments.length - 1;
          this.setData({ garments, activeGarment, backendConnected: true });
          if (this.data.sessionId) {
            await api.selectGarment(this.data.sessionId, custom.id);
            if (this.data.recentPersonImageId) {
              await this.refreshStaticTryOn(this.data.recentPersonImageId);
            } else {
              this.setData({ modeLabel: "衣服已加入 · 点击定格试穿" });
            }
          }
        } catch (error) {
          this.setData({ modeLabel: "加入失败，请检查图片和后端" });
          wx.showToast({ title: "衣服上传失败", icon: "none" });
        }
      }
    });
  },

  noop() {}
});
