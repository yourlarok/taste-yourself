// 统一的数据入口：演示模式走 mock，真实模式适配本项目 FastAPI 契约。
const env = require('../env.js');
const mock = require('./mock.js');

const TOKEN_KEY = 'ty_token';
let token = wx.getStorageSync(TOKEN_KEY) || '';
let loginPromise = null;

class ApiError extends Error {
  constructor(status, message, code) {
    super(message || '请求失败');
    this.status = status || 0;
    this.code = code || '';
  }
}

function saveToken(value) {
  token = value || '';
  wx.setStorageSync(TOKEN_KEY, token);
}

function normalizeLogin(response) {
  const normalized = Object.assign({}, response, {
    token: response.token || response.access_token || ''
  });
  saveToken(normalized.token);
  return normalized;
}

function login() {
  if (env.useMock) return mock.login().then(normalizeLogin);
  if (loginPromise) return loginPromise;
  loginPromise = realLogin().catch((error) => {
    loginPromise = null;
    throw error;
  });
  return loginPromise;
}

function realLogin() {
  const system = wx.getDeviceInfo ? wx.getDeviceInfo() : wx.getSystemInfoSync();
  if (system.platform === 'devtools') {
    return rawRequest('POST', '/api/v1/auth/dev-login', {}).then(normalizeLogin);
  }
  return new Promise((resolve, reject) => {
    wx.login({
      success: (result) => {
        rawRequest('POST', '/api/v1/auth/wechat', { code: result.code })
          .then((response) => resolve(normalizeLogin(response)))
          .catch(reject);
      },
      fail: () => reject(new ApiError(0, '微信登录失败，请重试', 'WX_LOGIN'))
    });
  });
}

function normalizeHttpError(response) {
  const body = response.data || {};
  let detail = body.message || body.detail || defaultMessage(response.statusCode);
  if (Array.isArray(detail)) detail = detail.map((item) => item.msg || '').filter(Boolean).join('；');
  return new ApiError(response.statusCode, detail, body.code || '');
}

function defaultMessage(status) {
  const messages = {
    401: '登录已过期，请重新登录',
    404: '内容不存在',
    409: '需要先建立尺寸画像',
    422: '图片或画面不符合要求',
    429: '今日次数已用完',
    503: '服务暂时不可用，请稍后重试'
  };
  return messages[status] || ('请求失败（' + status + '）');
}

function rawRequest(method, path, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: env.baseUrl + path,
      method,
      data: data || {},
      header: { 'content-type': 'application/json' },
      timeout: 20000,
      success: (response) => {
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(response.data || {});
        else reject(normalizeHttpError(response));
      },
      fail: () => reject(new ApiError(0, '网络连接失败，请检查网络后重试', 'NETWORK'))
    });
  });
}

// GET 在登录失效后只重放一次，避免重复执行写操作。
function request(method, path, data, replayed) {
  const call = () => new Promise((resolve, reject) => {
    wx.request({
      url: env.baseUrl + path,
      method,
      data: data || {},
      header: {
        'content-type': 'application/json',
        Authorization: token ? 'Bearer ' + token : ''
      },
      timeout: 30000,
      success: (response) => {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data || {});
        } else if (response.statusCode === 401 && !replayed && method === 'GET') {
          loginPromise = null;
          login().then(() => request(method, path, data, true)).then(resolve).catch(reject);
        } else {
          reject(normalizeHttpError(response));
        }
      },
      fail: () => reject(new ApiError(0, '网络连接失败，请检查网络后重试', 'NETWORK'))
    });
  });
  return token ? call() : login().then(call);
}

function uploadFile(path, filePath, fieldName, formData, onProgress) {
  if (!filePath) return Promise.reject(new ApiError(422, '没有获取到可上传的照片', 'MISSING_FILE'));
  const upload = () => new Promise((resolve, reject) => {
    const task = wx.uploadFile({
      url: env.baseUrl + path,
      filePath,
      name: fieldName || 'image',
      formData: formData || {},
      header: { Authorization: token ? 'Bearer ' + token : '' },
      timeout: 60000,
      success: (response) => {
        const body = safeParse(response.data);
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(body);
        else reject(normalizeHttpError({ statusCode: response.statusCode, data: body }));
      },
      fail: () => reject(new ApiError(0, '网络连接失败，上传未完成', 'NETWORK'))
    });
    if (onProgress && task && task.onProgressUpdate) {
      task.onProgressUpdate((progress) => onProgress(progress.progress));
    }
  });
  return token ? upload() : login().then(upload);
}

function safeParse(text) {
  try { return JSON.parse(text || '{}'); } catch (error) { return {}; }
}

function absoluteMediaUrl(value) {
  if (!value || /^https?:\/\//.test(value) || value.indexOf('/assets/') === 0) return value || '';
  return env.baseUrl.replace(/\/$/, '') + (value.indexOf('/') === 0 ? '' : '/') + value;
}

function normalizeGarment(item, source) {
  return Object.assign({}, item, {
    image_url: absoluteMediaUrl(item.image_url),
    source: item.source || source
  });
}

function normalizeGarmentList(response, source) {
  const items = Array.isArray(response) ? response : (response.garments || []);
  return { garments: items.map((item) => normalizeGarment(item, source)) };
}

function uncertaintyText(values) {
  const nums = Object.keys(values || {}).map((key) => Number(values[key])).filter((n) => Number.isFinite(n));
  return nums.length ? ('±' + Math.max.apply(null, nums).toFixed(1) + 'cm') : '±1.5cm';
}

const METRIC_LABELS = {
  chest_cm: '胸围', bust_cm: '胸围', waist_cm: '腰围', hip_cm: '臀围',
  shoulder_cm: '肩宽', length_cm: '衣长', sleeve_cm: '袖长'
};

function normalizeFit(response) {
  if (response.rows) return response;
  return {
    rows: (response.variants || []).map((variant) => ({
      size: variant.size_label,
      metrics: (variant.reasons || []).map((reason) => ({
        key: reason.measurement,
        label: METRIC_LABELS[reason.measurement] || reason.measurement,
        body: reason.body_cm,
        garment: reason.garment_cm,
        ease: reason.ease_cm,
        range: reason.target_ease_cm || null
      }))
    })),
    source: response.profile_source || '商家公开尺码表',
    error_margin: uncertaintyText(response.measurement_uncertainty_cm)
  };
}

function explainError(error, scene) {
  const status = error && error.status !== undefined ? error.status : -1;
  const base = { title: '出了点问题', desc: error && error.message ? error.message : '', actionText: '重试' };
  if (status === 0) return { title: '网络连接失败', desc: '当前内容都已保留，检查网络后可以重试。', actionText: '重试' };
  if (status === 401) return { title: '登录状态已失效', desc: '当前内容已保留，重新登录后即可继续。', actionText: '重新登录' };
  if (status === 404) return { title: '没有找到对应内容', desc: '它可能已被移除；当前页面其他内容不受影响。', actionText: '知道了' };
  if (status === 409) return { title: '需要尺寸画像', desc: '建立尺寸画像后即可查看尺码差异；不建立也不影响视觉试穿。', actionText: '了解' };
  if (status === 422) return {
    title: scene === 'upload' ? '图片未通过审核' : '画面不符合要求',
    desc: (error && error.message ? error.message + '。' : '') + '当前选择的衣服与结果都已保留，可按提示调整后重试。',
    actionText: '重试'
  };
  if (status === 429) return { title: '今日次数已用完', desc: '已生成的内容不受影响，明天会恢复额度。', actionText: '知道了' };
  if (status === 503) return { title: '服务暂时不可用', desc: '当前衣服、画面与结果都已保留，稍后再试即可。', actionText: '稍后重试' };
  return base;
}

const useMock = () => env.useMock;

const api = {
  ApiError,
  explainError,
  login,
  getToken: () => token,

  listCatalogGarments: () => useMock()
    ? mock.listCatalogGarments()
    : request('GET', '/api/v1/catalog/garments').then((r) => normalizeGarmentList(r, 'catalog')),
  listWardrobeGarments: () => useMock()
    ? mock.listWardrobeGarments()
    : request('GET', '/api/v1/wardrobe/garments').then((r) => normalizeGarmentList(r, 'wardrobe')),
  uploadWardrobeGarment: (filePath, onProgress) => useMock()
    ? mock.uploadWardrobeGarment(filePath, onProgress)
    : uploadFile('/api/v1/wardrobe/garments', filePath, 'image', {
        name: '新加入的衣服', category: 'tops'
      }, onProgress).then((item) => ({ garment: normalizeGarment(item, 'wardrobe') })),

  getRecentExperience: () => useMock()
    ? mock.getRecentExperience()
    : request('GET', '/api/v1/me/recent-experience').then((r) => Object.assign({}, r, {
        result_image: absoluteMediaUrl(r.result_image || r.result_url)
      })),
  getUsageInfo: () => useMock()
    ? mock.getUsageInfo()
    : request('GET', '/api/v1/me/usage').then((r) => ({
        static_used: r.static.used, static_limit: r.static.limit,
        realtime_used: r.realtime.used, realtime_limit: r.realtime.limit
      })),
  getCapabilities: () => useMock()
    ? mock.getCapabilities()
    : request('GET', '/api/v1/capabilities'),
  getFitProfile: () => useMock()
    ? mock.getFitProfile()
    : request('GET', '/api/v1/me/fit-profile').then((r) => Object.assign({}, r, {
        created_at: r.created_at || r.updated_at,
        source: r.source || r.provider,
        error_margin: r.error_margin || uncertaintyText(r.measurement_uncertainty_cm),
        measurements: r.measurements || r.measurements_cm
      })),
  deleteFitProfile: () => useMock() ? mock.deleteFitProfile() : request('DELETE', '/api/v1/me/fit-profile'),
  deleteAllData: () => useMock()
    ? mock.deleteAllData()
    : request('DELETE', '/api/v1/me/data', { confirmation: 'DELETE' }),

  createExperienceSession: (garmentId) => useMock()
    ? mock.createExperienceSession(garmentId)
    : request('POST', '/api/v1/experience-sessions', { garment_id: garmentId }),
  switchSessionGarment: (sessionId, garmentId) => useMock()
    ? mock.switchSessionGarment(sessionId, garmentId)
    : request('PUT', '/api/v1/experience-sessions/' + sessionId + '/garment', { garment_id: garmentId }),
  uploadPersonImage: (filePath) => useMock()
    ? mock.uploadPersonImage(filePath)
    : uploadFile('/api/v1/person-images', filePath, 'image'),
  staticTryon: (sessionId, garmentId, personImageId) => useMock()
    ? mock.staticTryon(sessionId, garmentId)
    : request('POST', '/api/v1/experience-sessions/' + sessionId + '/static-tryon', {
        person_image_id: personImageId || null
      }).then((r) => {
        if (r.status !== 'completed') {
          throw new ApiError(503, r.notice || '试穿照生成失败', 'TRYON_FAILED');
        }
        return Object.assign({}, r, {
          result_image: r.result_url
            ? absoluteMediaUrl(r.result_url)
            : r.provider === 'mock'
              ? '/assets/demo/tryon-result.jpg'
              : ''
        });
      }),

  getFitAnalysis: (garmentId) => useMock()
    ? mock.getFitAnalysis(garmentId)
    : request('GET', '/api/v1/catalog/garments/' + garmentId + '/fit-analysis').then(normalizeFit),

  createBodyScan: (sessionId) => useMock()
    ? mock.createBodyScan(sessionId)
    : request('POST', '/api/v1/body-scans', { experience_session_id: sessionId, consented: true }),
  uploadScanFrame: (scanId, filePath, side) => useMock()
    ? mock.uploadScanFrame(scanId, filePath, side)
    : uploadFile('/api/v1/body-scans/' + scanId + '/frames', filePath, 'image', { angle: side }),
  completeBodyScan: (scanId) => useMock()
    ? mock.completeBodyScan(scanId)
    : request('POST', '/api/v1/body-scans/' + scanId + '/complete'),

  startRealtime: (sessionId) => useMock()
    ? mock.startRealtime(sessionId)
    : request('POST', '/api/v1/experience-sessions/' + sessionId + '/realtime').then((r) => Object.assign({}, r, {
        duration: r.duration || r.max_duration_seconds || 15
      })),
  // 当前后端令牌会自动过期；前端停止本地播放和倒计时即可。
  stopRealtime: (sessionId) => useMock() ? mock.stopRealtime(sessionId) : Promise.resolve({ stopped: true })
};

module.exports = api;
