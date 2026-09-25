// services/mock.js — 本地演示数据层
// 与 api.js 暴露完全一致的接口；通过 env.js 的 mockScenario 切换不同验收场景。
// 演示数据持久化在本地 storage 中：试穿一次后回到首页即可看到“有最近试穿”的首页态。

const env = require('../env.js');

const K = {
  wardrobe: 'mock_wardrobe',
  recent: 'mock_recent',
  profile: 'mock_profile',
  session: 'mock_session'
};

function usageKey() {
  const d = new Date();
  return 'mock_usage_' + d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
}

/* ---------------- 演示数据 ---------------- */

const RESULT_IMAGE = '/assets/demo/tryon-result.jpg';

const CATALOG = [
  { id: 'g-cardigan', name: '燕麦色针织开衫', image_url: '/assets/demo/garment-cardigan.jpg', source: 'demo' },
  { id: 'g-blazer', name: '藏青色西装外套', image_url: '/assets/demo/garment-blazer.jpg', source: 'demo' },
  { id: 'g-shirt', name: '米白色棉质衬衫', image_url: '/assets/demo/garment-shirt.jpg', source: 'demo' },
  { id: 'g-dress', name: '黑色 A 字连衣裙', image_url: '/assets/demo/garment-dress.jpg', source: 'demo' }
];

const WARDROBE_SEED = [
  { id: 'w-hoodie', name: '浅灰连帽卫衣', image_url: '/assets/demo/wardrobe-hoodie.jpg', source: 'wardrobe' },
  { id: 'w-trench', name: '卡其色风衣', image_url: '/assets/demo/wardrobe-trench.jpg', source: 'wardrobe' }
];

// 商品原始尺码数据（按商品原始顺序，例如 M、L、XL）；缺失的商品视为“暂无尺码数据”。
// 数值单位 cm；range 为常见参考余量区间，仅用于展示相对位置，不构成推荐。
const SIZE_SPECS = {
  'g-cardigan': {
    sizes: ['M', 'L', 'XL'],
    dims: {
      M: { bust: 100, waist: 96, shoulder: 40, length: 58 },
      L: { bust: 104, waist: 100, shoulder: 41, length: 60 },
      XL: { bust: 108, waist: 104, shoulder: 42, length: 62 }
    }
  },
  'g-blazer': {
    sizes: ['M', 'L', 'XL'],
    dims: {
      M: { bust: 98, waist: 88, shoulder: 42, length: 70 },
      L: { bust: 102, waist: 92, shoulder: 43, length: 72 },
      XL: { bust: 106, waist: 96, shoulder: 44, length: 74 }
    }
  },
  'g-shirt': {
    sizes: ['M', 'L', 'XL'],
    dims: {
      M: { bust: 104, waist: 100, shoulder: 45, length: 68 },
      L: { bust: 108, waist: 104, shoulder: 46, length: 70 },
      XL: { bust: 112, waist: 108, shoulder: 47, length: 72 }
    }
  },
  'g-dress': {
    sizes: ['M', 'L', 'XL'],
    dims: {
      M: { bust: 90, waist: 76, shoulder: 37, length: 108 },
      L: { bust: 94, waist: 80, shoulder: 38, length: 110 },
      XL: { bust: 98, waist: 84, shoulder: 39, length: 112 }
    }
  },
  'w-hoodie': {
    sizes: ['M', 'L', 'XL'],
    dims: {
      M: { bust: 112, waist: 108, shoulder: 50, length: 66 },
      L: { bust: 116, waist: 112, shoulder: 51, length: 68 },
      XL: { bust: 120, waist: 116, shoulder: 52, length: 70 }
    }
  }
  // w-trench 故意缺失：用于验收“商品尺码数据缺失”态
};

const METRIC_META = [
  { key: 'bust', label: '胸围', range: [8, 14] },
  { key: 'waist', label: '腰围', range: [6, 12] },
  { key: 'shoulder', label: '肩宽', range: [1, 3] },
  { key: 'length', label: '衣长', range: null }
];

const SCAN_RESULT_PROFILE = {
  created_at: 0,
  source: '轮廓扫描',
  error_margin: '±1.5cm',
  measurements: { height: 165, shoulder: 39, bust: 88, waist: 72, hip: 94 }
};

/* ---------------- 工具 ---------------- */

function delay(ms) {
  const d = typeof ms === 'number' ? ms : env.mockLatency;
  return new Promise((resolve) => setTimeout(resolve, d));
}

class MockError extends Error {
  constructor(status, message, code) {
    super(message);
    this.status = status;
    this.code = code || '';
  }
}

function scenario() {
  return env.mockScenario || 'normal';
}

function guardNetwork() {
  if (scenario() === 'offline') {
    throw new MockError(0, '网络连接失败，请检查网络后重试', 'NETWORK');
  }
}

function read(key, fallback) {
  const v = wx.getStorageSync(key);
  return v === '' || v === undefined || v === null ? fallback : v;
}

function write(key, value) {
  wx.setStorageSync(key, value);
}

function getUsage() {
  return read(usageKey(), { static_used: 0, static_limit: 10, realtime_used: 0, realtime_limit: 3 });
}

function bumpUsage(field) {
  const u = getUsage();
  u[field] = (u[field] || 0) + 1;
  write(usageKey(), u);
  return u;
}

/* ---------------- 接口实现（与 api.js 同构） ---------------- */

function login() {
  return delay(300).then(() => {
    guardNetwork();
    return { token: 'mock-token', user: { nickname: '演示用户' } };
  });
}

function listCatalogGarments() {
  return delay().then(() => {
    guardNetwork();
    return { garments: CATALOG.slice() };
  });
}

function listWardrobeGarments() {
  return delay().then(() => {
    guardNetwork();
    return { garments: read(K.wardrobe, WARDROBE_SEED.slice()) };
  });
}

function uploadWardrobeGarment(filePath, onProgress) {
  if (onProgress) {
    let p = 0;
    const timer = setInterval(() => {
      p += 25;
      if (p >= 100) clearInterval(timer);
      onProgress(Math.min(p, 100));
    }, 220);
  }
  return delay(1600).then(() => {
    guardNetwork();
    if (scenario() === 'upload_rejected') {
      throw new MockError(422, '内容审核未通过：请上传单件衣服的清晰图片', 'MODERATION');
    }
    const list = read(K.wardrobe, WARDROBE_SEED.slice());
    const item = {
      id: 'w-' + Date.now(),
      name: '新上传的衣服',
      image_url: filePath,
      source: 'wardrobe'
    };
    list.push(item);
    write(K.wardrobe, list);
    return { garment: item };
  });
}

function getRecentExperience() {
  return delay().then(() => {
    guardNetwork();
    const recent = read(K.recent, null);
    if (!recent) throw new MockError(404, '暂无试穿记录', 'NOT_FOUND');
    return recent;
  });
}

function getUsageInfo() {
  return delay().then(() => {
    guardNetwork();
    return getUsage();
  });
}

function getFitProfile() {
  return delay().then(() => {
    guardNetwork();
    const p = read(K.profile, null);
    if (!p) throw new MockError(404, '尚未建立尺寸画像', 'NOT_FOUND');
    return p;
  });
}

function deleteFitProfile() {
  return delay().then(() => {
    guardNetwork();
    wx.removeStorageSync(K.profile);
    return { deleted: true };
  });
}

function deleteAllData() {
  return delay(900).then(() => {
    guardNetwork();
    wx.removeStorageSync(K.wardrobe);
    wx.removeStorageSync(K.recent);
    wx.removeStorageSync(K.profile);
    wx.removeStorageSync(K.session);
    wx.removeStorageSync(usageKey());
    return { deleted: true };
  });
}

function createExperienceSession(garmentId) {
  return delay().then(() => {
    guardNetwork();
    const s = { id: 's-' + Date.now(), garment_id: garmentId || null, created_at: Date.now() };
    write(K.session, s);
    return s;
  });
}

function switchSessionGarment(sessionId, garmentId) {
  return delay(200).then(() => {
    guardNetwork();
    return { id: sessionId, garment_id: garmentId };
  });
}

function uploadPersonImage() {
  return delay(700).then(() => {
    guardNetwork();
    return { id: 'p-' + Date.now() };
  });
}

function staticTryon(sessionId, garmentId) {
  return delay(2400).then(() => {
    guardNetwork();
    if (scenario() === 'quota') {
      throw new MockError(429, '今日静态试穿次数已用完', 'QUOTA');
    }
    if (scenario() === 'server_busy') {
      throw new MockError(503, '试穿服务暂不可用，请稍后重试', 'PROVIDER_DOWN');
    }
    bumpUsage('static_used');
    const all = CATALOG.concat(read(K.wardrobe, WARDROBE_SEED.slice()));
    const g = all.find((x) => x.id === garmentId) || all[0];
    const recent = {
      session_id: sessionId,
      garment_id: g.id,
      garment_name: g.name,
      result_image: RESULT_IMAGE,
      updated_at: Date.now()
    };
    write(K.recent, recent);
    return { result_image: RESULT_IMAGE, session_id: sessionId };
  });
}

function getFitAnalysis(garmentId) {
  return delay(700).then(() => {
    guardNetwork();
    const spec = SIZE_SPECS[garmentId];
    if (!spec) throw new MockError(404, '该商品暂无尺码数据', 'NO_PRODUCT_DATA');
    const profile = read(K.profile, null);
    if (!profile) throw new MockError(409, '需要先建立尺寸画像', 'PROFILE_REQUIRED');
    const body = profile.measurements;
    const rows = spec.sizes.map((size) => {
      const dims = spec.dims[size];
      const metrics = METRIC_META.map((meta) => {
        const garmentVal = dims[meta.key];
        const bodyVal = meta.key === 'length' ? null : body[meta.key];
        const ease = bodyVal === null || bodyVal === undefined ? null : garmentVal - bodyVal;
        return {
          key: meta.key,
          label: meta.label,
          body: bodyVal,
          garment: garmentVal,
          ease,
          range: meta.range ? meta.range.slice() : null
        };
      });
      return { size, metrics };
    });
    return {
      garment_id: garmentId,
      size_order: spec.sizes.slice(),
      source: '商家公开尺码表',
      error_margin: profile.error_margin || '±1.5cm',
      profile_created_at: profile.created_at,
      rows
    };
  });
}

let scanCounter = 0;

function createBodyScan() {
  return delay().then(() => {
    guardNetwork();
    scanCounter += 1;
    return { id: 'scan-' + Date.now() };
  });
}

function uploadScanFrame(scanId, filePath, side) {
  return delay(900).then(() => {
    guardNetwork();
    return { id: scanId, side, accepted: true };
  });
}

function completeBodyScan(scanId) {
  return delay(2000).then(() => {
    guardNetwork();
    if (scenario() === 'scan_retake' && scanCounter % 2 === 1) {
      throw new MockError(422, '侧面画面不完整：请露出全身并远离杂物', 'RETAKE_SIDE');
    }
    const profile = Object.assign({}, SCAN_RESULT_PROFILE, { created_at: Date.now() });
    write(K.profile, profile);
    return { profile };
  });
}

function startRealtime(sessionId) {
  return delay(1400).then(() => {
    guardNetwork();
    if (scenario() === 'quota') {
      throw new MockError(429, '今日动态试衣次数已用完', 'QUOTA');
    }
    if (scenario() === 'server_busy') {
      throw new MockError(503, '动态试衣服务暂不可用', 'PROVIDER_DOWN');
    }
    bumpUsage('realtime_used');
    return { session_id: sessionId, realtime_id: 'rt-' + Date.now(), duration: 15 };
  });
}

function stopRealtime(sessionId) {
  return delay(200).then(() => ({ session_id: sessionId, stopped: true }));
}

module.exports = {
  MockError,
  login,
  listCatalogGarments,
  listWardrobeGarments,
  uploadWardrobeGarment,
  getRecentExperience,
  getUsageInfo,
  getFitProfile,
  deleteFitProfile,
  deleteAllData,
  createExperienceSession,
  switchSessionGarment,
  uploadPersonImage,
  staticTryon,
  getFitAnalysis,
  createBodyScan,
  uploadScanFrame,
  completeBodyScan,
  startRealtime,
  stopRealtime
};
