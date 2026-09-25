// 镜前 — 相机是核心画布。
// 页面状态机：
//   studio: preparing | camera | capturing | generating | result | degraded
//   fit:    idle | profile_required | loading | ready | missing_product_data | error
//   scan:   consent | front | side | uploading | processing | needs_retake | completed | failed
//   realtime: idle | connecting | active | ending | unavailable
const api = require('../../services/api.js');

const app = getApp();
const REALTIME_SECONDS = 15;

// 由 phase / cameraAuth / quotaUsed 派生的渲染状态（避免在 WXML 写复杂表达式）
function derive(d) {
  const inResult = d.phase === 'result';
  const showCamera = !inResult && (d.cameraAuth === 'unknown' || d.cameraAuth === 'ok');
  const generateDisabled =
    d.phase === 'degraded' || d.phase === 'preparing' || d.quotaUsed || !d.selectedGarmentId;
  let cameraTip = '';
  if (d.cameraAuth === 'denied') {
    cameraTip = '相机权限未开启，暂时无法实时取景；仍可选择衣服生成试穿照。';
  } else if (d.cameraAuth === 'unsupported') {
    cameraTip = '当前环境不支持相机；仍可选择衣服生成试穿照。';
  }
  return { showCamera, generateDisabled, cameraTip };
}

function statusLineOf(phase) {
  switch (phase) {
    case 'preparing': return '正在准备…';
    case 'capturing': return '正在取景…';
    case 'generating': return '正在生成…';
    case 'result': return '结果已更新';
    case 'degraded': return '离线状态';
    default: return '选择衣服后生成试穿照';
  }
}

Page({
  data: {
    layout: null,
    reduceMotion: false,
    // studio
    phase: 'preparing',
    statusLine: '正在准备…',
    cameraAuth: 'unknown',       // unknown | ok | denied | unsupported
    showCamera: false,
    cameraTip: '',
    banner: { show: false, title: '', desc: '', actionText: '' },
    sessionId: '',
    catalog: [],
    wardrobe: [],
    selectedGarmentId: '',
    selectedGarmentName: '',
    uploading: false,
    uploadPercent: 0,
    uploadError: '',             // '' | 'failed' | 'rejected'
    generatingText: '正在生成…',
    resultImage: '',
    resultTimeText: '',
    quotaUsed: false,
    quotaHint: '',
    generateDisabled: true,
    // fit
    fitVisible: false,
    fitState: 'idle',
    fitRows: [],
    fitSourceText: '',
    fitErrorTitle: '',
    fitErrorDesc: '',
    // scan
    scanVisible: false,
    scanState: 'consent',
    scanRetakeSide: 'side',
    scanFailTitle: '',
    scanFailDesc: '',
    processingStep: 0,
    // realtime
    realtimeState: 'idle',
    countdown: REALTIME_SECONDS,
    realtimePublishUrl: '',
    realtimePlayUrl: '',
    realtimeHasStream: false
  },

  patch(obj) {
    const merged = Object.assign({}, this.data, obj);
    this.setData(Object.assign({}, obj, derive(merged)));
  },

  /* ================= 生命周期 ================= */

  onLoad(options) {
    this._pendingAdd = !!(options && options.add === '1');
    this._scanId = '';
    this._rtTimer = null;
    this.setData({
      layout: app.globalData.layout,
      reduceMotion: app.globalData.reduceMotion
    });
    this.init();
  },

  onHide() {
    // 切后台：终止动态会话与计时器；静态上下文（衣服、结果）全部保留
    this.stopRealtimeSession(true);
  },

  onUnload() {
    this.clearRtTimer();
  },

  /* ================= 初始化 ================= */

  init() {
    this.patch({ phase: 'preparing', statusLine: statusLineOf('preparing') });
    app.ensureLogin()
      .then(() => Promise.all([
        api.listCatalogGarments(),
        api.listWardrobeGarments()
      ]))
      .then((results) => {
        const catalog = results[0].garments || [];
        const wardrobe = results[1].garments || [];
        const first = catalog[0] || wardrobe[0] || null;
        if (!first) throw new api.ApiError(404, '还没有可试穿的衣服', 'EMPTY_GARMENTS');
        return api.createExperienceSession(first.id).then((session) => ({ session, catalog, wardrobe, first }));
      })
      .then((context) => {
        const session = context.session;
        const catalog = context.catalog;
        const wardrobe = context.wardrobe;
        const first = context.first;
        this.patch({
          phase: 'camera',
          statusLine: statusLineOf('camera'),
          sessionId: session.id,
          catalog,
          wardrobe,
          selectedGarmentId: first ? first.id : '',
          selectedGarmentName: first ? first.name : '',
          banner: { show: false, title: '', desc: '', actionText: '' }
        });
        this.prepareCamera();
        if (this._pendingAdd) {
          this._pendingAdd = false;
          this.onAddGarment();
        }
      })
      .catch((err) => {
        const info = api.explainError(err, 'init');
        this.patch({
          phase: 'degraded',
          statusLine: statusLineOf('degraded'),
          banner: { show: true, title: info.title, desc: info.desc, actionText: '重新连接' }
        });
      });
  },

  onBannerAction() {
    if (this.data.phase === 'degraded') {
      this.init();
    } else {
      this.hideBanner();
    }
  },

  onBannerClose() {
    this.hideBanner();
  },

  showBanner(err, scene) {
    const info = api.explainError(err, scene);
    this.setData({ banner: { show: true, title: info.title, desc: info.desc, actionText: '' } });
  },

  hideBanner() {
    this.setData({ banner: { show: false, title: '', desc: '', actionText: '' } });
  },

  /* ================= 相机 ================= */

  // 进入镜前即需要取景 —— 在此刻申请相机权限，而非启动页
  prepareCamera() {
    wx.getSetting({
      success: (res) => {
        const granted = res.authSetting['scope.camera'];
        if (granted === true) {
          this.patch({ cameraAuth: 'ok' });
        } else if (granted === false) {
          this.patch({ cameraAuth: 'denied' });
        } else {
          wx.authorize({
            scope: 'scope.camera',
            success: () => this.patch({ cameraAuth: 'ok' }),
            fail: () => this.patch({ cameraAuth: 'denied' })
          });
        }
      },
      fail: () => this.patch({ cameraAuth: 'unknown' })
    });
  },

  onCameraInit() {
    if (this.data.cameraAuth === 'unknown') this.patch({ cameraAuth: 'ok' });
  },

  onCameraError(e) {
    const msg = (e && e.detail && e.detail.errMsg) || '';
    const denied = /auth|permission|authorize/i.test(msg);
    this.patch({ cameraAuth: denied ? 'denied' : 'unsupported' });
  },

  onOpenSetting() {
    wx.openSetting({
      success: (res) => {
        if (res.authSetting && res.authSetting['scope.camera']) {
          this.patch({ cameraAuth: 'ok' });
        }
      }
    });
  },

  takePersonPhoto() {
    if (this.data.cameraAuth !== 'ok') return Promise.resolve(null);
    return new Promise((resolve) => {
      wx.createCameraContext().takePhoto({
        quality: 'high',
        success: (r) => resolve(r.tempImagePath),
        fail: () => resolve(null)
      });
    });
  },

  /* ================= 衣服 ================= */

  onSelectGarment(e) {
    const id = e.detail.id;
    const all = this.data.catalog.concat(this.data.wardrobe);
    const g = all.find((x) => x.id === id);
    if (!g) return;
    this.patch({
      selectedGarmentId: g.id,
      selectedGarmentName: g.name,
      quotaUsed: false,
      quotaHint: ''
    });
    if (this.data.sessionId) {
      api.switchSessionGarment(this.data.sessionId, g.id).catch(() => {});
    }
  },

  onAddGarment() {
    wx.showModal({
      title: '衣服图要求',
      content: '平铺或挂拍、画面内仅一件衣物、背景简洁、光线均匀，效果更好。',
      confirmText: '选择图片',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) this.chooseAndUpload();
      }
    });
  },

  onRetryUpload() {
    this.setData({ uploadError: '' });
    this.chooseAndUpload();
  },

  chooseAndUpload() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0];
        if (!file || !file.tempFilePath) return;
        this.setData({ uploading: true, uploadPercent: 0, uploadError: '' });
        api.uploadWardrobeGarment(file.tempFilePath, (p) => {
          this.setData({ uploadPercent: Math.round(p) });
        }).then((r) => {
          const item = r.garment;
          const wardrobe = this.data.wardrobe.concat([item]);
          this.setData({ uploading: false });
          this.patch({ wardrobe });
          this.onSelectGarment({ detail: { id: item.id } });
          wx.showToast({ title: '已加入衣橱', icon: 'success' });
        }).catch((err) => {
          this.setData({
            uploading: false,
            uploadError: err && err.status === 422 ? 'rejected' : 'failed'
          });
        });
      }
    });
  },

  /* ================= 静态试穿 ================= */

  onGenerate() {
    const d = this.data;
    if (!d.sessionId || d.phase === 'generating' || d.phase === 'capturing') return;
    this.hideBanner();

    // 1) 取景（相机不可用 / 演示模式下跳过，由后端或演示层处理）
    this.patch({ phase: 'capturing', statusLine: statusLineOf('capturing'), generatingText: '上传画面…' });
    this.takePersonPhoto()
      .then((photoPath) => {
        // 2) 上传本人画面
        this.patch({ phase: 'generating', statusLine: statusLineOf('generating') });
        return api.uploadPersonImage(photoPath);
      })
      .then((person) => {
        // 3) 生成试穿照
        this.setData({ generatingText: '正在生成试穿照…' });
        return api.staticTryon(d.sessionId, d.selectedGarmentId, person && person.id);
      })
      .then((r) => {
        this.patch({
          phase: 'result',
          statusLine: statusLineOf('result'),
          resultImage: r.result_image,
          resultTimeText: '刚刚',
          quotaUsed: false,
          quotaHint: ''
        });
      })
      .catch((err) => {
        // 失败：相机、衣服与已有结果全部保留，可重试
        const backTo = this.data.resultImage ? 'result' : 'camera';
        if (err && err.status === 429) {
          this.patch({
            phase: backTo,
            statusLine: statusLineOf(backTo),
            quotaUsed: true,
            quotaHint: '今日静态试穿次数已用完，明天再来。'
          });
        } else {
          this.patch({ phase: backTo, statusLine: statusLineOf(backTo) });
          this.showBanner(err, 'tryon');
        }
      });
  },

  // 点击结果图回到相机：明确提示结果已保留
  onTapResult() {
    wx.showModal({
      title: '返回相机取景？',
      content: '试穿结果已保留，可以随时回来看。',
      confirmText: '返回相机',
      cancelText: '再看看',
      success: (res) => {
        if (res.confirm) {
          this.patch({ phase: 'camera', statusLine: statusLineOf('camera') });
        }
      }
    });
  },

  onSave() {
    const src = this.data.resultImage;
    if (!src) return;
    // 保存权限在执行动作时申请
    wx.authorize({
      scope: 'scope.writePhotosAlbum',
      success: () => this.saveImage(src),
      fail: () => {
        wx.showModal({
          title: '需要相册权限',
          content: '开启后才能把试穿照保存到相册。',
          confirmText: '去开启',
          success: (res) => {
            if (res.confirm) wx.openSetting();
          }
        });
      }
    });
  },

  saveImage(src) {
    this.resolveLocalFile(src)
      .then((path) => new Promise((resolve, reject) => {
        wx.saveImageToPhotosAlbum({
          filePath: path,
          success: resolve,
          fail: reject
        });
      }))
      .then(() => wx.showToast({ title: '已保存到相册', icon: 'success' }))
      .catch(() => wx.showToast({ title: '保存失败，可截屏保存', icon: 'none' }));
  },

  resolveLocalFile(src) {
    return new Promise((resolve, reject) => {
      if (/^https?:\/\//.test(src)) {
        wx.downloadFile({ url: src, success: (r) => resolve(r.tempFilePath), fail: reject });
        return;
      }
      try {
        const fs = wx.getFileSystemManager();
        const dest = wx.env.USER_DATA_PATH + '/tryon-' + Date.now() + '.jpg';
        fs.copyFileSync(src, dest);
        resolve(dest);
      } catch (e) {
        reject(e);
      }
    });
  },

  /* ================= 尺码差异抽屉 ================= */

  onOpenFit() {
    this.setData({ fitVisible: true });
    this.loadFit();
  },

  onFitClose() {
    this.setData({ fitVisible: false, fitState: 'idle' });
  },

  onFitSkip() {
    this.onFitClose();
  },

  onFitRetry() {
    this.loadFit();
  },

  loadFit() {
    this.setData({ fitState: 'loading' });
    api.getFitAnalysis(this.data.selectedGarmentId)
      .then((res) => {
        this.setData({
          fitState: 'ready',
          fitRows: this.buildFitRows(res.rows || []),
          fitSourceText:
            '数据来源：' + (res.source || '商家公开尺码表') +
            ' · 测量误差约 ' + (res.error_margin || '±1.5cm') +
            '。轮廓扫描存在个体差异，结果仅反映测量时刻的状态；余量为“成衣尺寸 − 身体尺寸”，区间仅为常见参考范围。'
        });
      })
      .catch((err) => {
        if (err && err.status === 409) {
          this.setData({ fitState: 'profile_required' });
        } else if (err && err.status === 404) {
          this.setData({ fitState: 'missing_product_data' });
        } else {
          const info = api.explainError(err, 'fit');
          this.setData({ fitState: 'error', fitErrorTitle: info.title, fitErrorDesc: info.desc });
        }
      });
  },

  // 计算每个尺码的展示数据：余量、相对参考区间位置、可视化参数、中立说明
  buildFitRows(rows) {
    return rows.map((row) => {
      const metrics = row.metrics.map((m) => {
        if (m.ease === null || m.ease === undefined || !m.range) {
          return {
            label: m.label,
            numsText: '衣服 ' + m.garment + 'cm',
            hasRange: false
          };
        }
        const ease = m.ease;
        const lo = m.range[0];
        const hi = m.range[1];
        const domain = Math.max(hi * 1.6, ease * 1.25, 1);
        const clamp = (v) => Math.max(2, Math.min(98, v));
        const position = ease < lo ? '低于参考区间' : ease > hi ? '高于参考区间' : '在参考区间内';
        return {
          label: m.label,
          numsText: '身体 ' + m.body + ' · 衣服 ' + m.garment + ' · 余量 ' + (ease >= 0 ? '+' : '') + ease + 'cm',
          hasRange: true,
          bandLeft: Math.round((lo / domain) * 100),
          bandWidth: Math.round(((hi - lo) / domain) * 100),
          dotPct: Math.round(clamp((ease / domain) * 100)),
          rangeText: lo + '–' + hi + 'cm',
          positionText: position,
          position
        };
      });
      const bust = metrics.find((m) => m.label === '胸围') || {};
      const waist = metrics.find((m) => m.label === '腰围') || {};
      const withEase = row.metrics.filter((m) => m.ease !== null && m.ease !== undefined);
      const summary = withEase
        .slice(0, 2)
        .map((m) => m.label + '余量 ' + (m.ease >= 0 ? '+' : '') + m.ease + 'cm')
        .join(' · ');
      return {
        size: row.size,
        tag: bust.positionText || '暂无对比',
        tone: bust.position === '在参考区间内' ? 'within' : 'outside',
        summary,
        metrics,
        note: neutralNote(bust.position, waist.position)
      };
    });
  },

  /* ================= 尺寸画像采集 ================= */

  onStartScan() {
    this.setData({ fitVisible: false, fitState: 'idle', scanVisible: true, scanState: 'consent' });
  },

  onScanAgree() {
    api.createBodyScan(this.data.sessionId)
      .then((s) => {
        this._scanId = s.id;
        this.setData({ scanState: 'front' });
      })
      .catch((err) => {
        const info = api.explainError(err, 'scan');
        this.setData({ scanState: 'failed', scanFailTitle: info.title, scanFailDesc: info.desc });
      });
  },

  onScanCaptured(e) {
    const side = e.detail.side;
    const scanComp = this.selectComponent('#scanGuide');
    const photoPromise = scanComp && scanComp.takePhoto
      ? scanComp.takePhoto().catch(() => null)
      : Promise.resolve(null);

    photoPromise
      .then((photoPath) => api.uploadScanFrame(this._scanId, photoPath, side))
      .then(() => {
        if (side === 'front') {
          this.setData({ scanState: 'side' });
        } else {
          this.finishScan();
        }
      })
      .catch((err) => {
        const info = api.explainError(err, 'scan');
        this.setData({ scanState: 'failed', scanFailTitle: info.title, scanFailDesc: info.desc });
      });
  },

  finishScan() {
    this.setData({ scanState: 'processing', processingStep: 0 });
    setTimeout(() => this.setData({ processingStep: 1 }), 700);
    api.completeBodyScan(this._scanId)
      .then(() => {
        this.setData({ processingStep: 2 });
        setTimeout(() => {
          this.setData({ processingStep: 3, scanState: 'completed' });
        }, 600);
      })
      .catch((err) => {
        if (err && err.status === 422) {
          // 只需要补拍具体角度
          this.setData({
            scanState: 'needs_retake',
            scanRetakeSide: /front|正面/.test(err.message || '') ? 'front' : 'side'
          });
        } else {
          const info = api.explainError(err, 'scan');
          this.setData({ scanState: 'failed', scanFailTitle: info.title, scanFailDesc: info.desc });
        }
      });
  },

  onScanRetake(e) {
    this.setData({ scanState: e.detail.side || this.data.scanRetakeSide });
  },

  onScanRetry() {
    this.setData({ scanState: 'consent' });
  },

  onScanFinish() {
    // 画像已建立：回到尺码抽屉并展示完整分析
    this.setData({ scanVisible: false, scanState: 'consent', fitVisible: true });
    this.loadFit();
  },

  onScanCancel() {
    const st = this.data.scanState;
    const close = () => {
      // 回到原试穿上下文：衣服、结果、抽屉状态都不受影响
      this.setData({ scanVisible: false, scanState: 'consent', fitVisible: true, fitState: 'profile_required' });
    };
    if (st === 'front' || st === 'side' || st === 'uploading' || st === 'processing') {
      wx.showModal({
        title: '取消本次扫描？',
        content: '已采集的进度不会保留，可以随时重新开始。',
        confirmText: '取消扫描',
        cancelText: '继续',
        success: (res) => {
          if (res.confirm) close();
        }
      });
    } else {
      close();
    }
  },

  onScanBackground() {
    // 页面切后台：终止扫描计时器，回到试穿上下文
    if (this.data.scanVisible) {
      this.setData({ scanVisible: false, scanState: 'consent' });
      wx.showToast({ title: '扫描已中断，可重新开始', icon: 'none' });
    }
  },

  /* ================= 15 秒动态试衣 ================= */

  onStartRealtime() {
    wx.showModal({
      title: '动态试衣 · 15 秒',
      content: '这是一段 15 秒的可选体验，会消耗较多流量；随时可以提前结束。',
      confirmText: '开始',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) this.connectRealtime();
      }
    });
  },

  connectRealtime() {
    this.hideBanner();
    this.setData({
      realtimeState: 'connecting',
      countdown: REALTIME_SECONDS,
      realtimePublishUrl: '',
      realtimePlayUrl: '',
      realtimeHasStream: false
    });
    api.startRealtime(this.data.sessionId)
      .then((r) => {
        if (r && r.status === 'unavailable') {
          throw new api.ApiError(503, r.notice || '动态试衣服务暂不可用', 'REALTIME_UNAVAILABLE');
        }
        const total = (r && r.duration) || REALTIME_SECONDS;
        const publishUrl = (r && r.publish_url) || '';
        const playUrl = (r && r.play_url) || '';
        this.setData({
          realtimeState: 'active',
          countdown: Math.min(total, REALTIME_SECONDS),
          realtimePublishUrl: publishUrl,
          realtimePlayUrl: playUrl,
          realtimeHasStream: !!(publishUrl && playUrl)
        });
        this.clearRtTimer();
        this._rtTimer = setInterval(() => {
          const left = this.data.countdown - 1;
          if (left <= 0) {
            this.stopRealtimeSession(false);
          } else {
            this.setData({ countdown: left });
          }
        }, 1000);
      })
      .catch((err) => {
        // 失败不清空衣服、静态结果与尺码分析上下文
        this.setData({ realtimeState: 'idle' });
        this.showBanner(err, 'realtime');
      });
  },

  onRealtimeMediaError(e) {
    if (this.data.realtimeState !== 'active' && this.data.realtimeState !== 'connecting') return;
    const detail = e && e.detail ? e.detail : {};
    this.clearRtTimer();
    this.setData({
      realtimeState: 'idle',
      countdown: REALTIME_SECONDS,
      realtimePublishUrl: '',
      realtimePlayUrl: '',
      realtimeHasStream: false
    });
    this.showBanner(
      new api.ApiError(503, detail.errMsg || '动态画面连接中断', 'REALTIME_MEDIA_ERROR'),
      'realtime'
    );
  },

  onEndRealtime() {
    if (this.data.realtimeState === 'active') {
      this.stopRealtimeSession(false);
    }
  },

  stopRealtimeSession(silent) {
    const st = this.data.realtimeState;
    if (st === 'idle') return;
    this.clearRtTimer();
    const sessionId = this.data.sessionId;
    this.setData({ realtimeState: silent ? 'idle' : 'ending' });
    api.stopRealtime(sessionId)
      .catch(() => {})
      .then(() => {
        this.setData({
          realtimeState: 'idle',
          countdown: REALTIME_SECONDS,
          realtimePublishUrl: '',
          realtimePlayUrl: '',
          realtimeHasStream: false,
          statusLine: this.data.phase === 'result' ? statusLineOf('result') : statusLineOf('camera')
        });
      });
  },

  clearRtTimer() {
    if (this._rtTimer) {
      clearInterval(this._rtTimer);
      this._rtTimer = null;
    }
  },

  /* ================= 其他 ================= */

  onBack() {
    wx.navigateBack({ fail: () => wx.reLaunch({ url: '/pages/home/home' }) });
  }
});

// 中立说明：只描述余量与区间的相对关系，不评价对错、不给出选择建议
function neutralNote(bustPos, waistPos) {
  const parts = [];
  if (bustPos) parts.push('胸围' + bustPos);
  if (waistPos && waistPos !== bustPos) parts.push('腰围' + waistPos);
  if (parts.length === 0) return '该尺码暂无可对比的身体数据。';
  return parts.join('，') + '。以上为测量差值的客观展示，是否合身因个人穿着习惯而异。';
}
