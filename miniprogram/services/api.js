function request(path, options = {}) {
  const app = getApp();
  const ready = app.globalData.authReady || Promise.resolve();
  return ready.catch(() => null).then(() => new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.apiBaseUrl}${path}`,
      method: options.method || "GET",
      data: options.data,
      header: app.globalData.accessToken
        ? { Authorization: `Bearer ${app.globalData.accessToken}` }
        : {},
      timeout: 5000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data);
          return;
        }
        const error = new Error(
          response.data && response.data.detail
            ? response.data.detail
            : `API ${response.statusCode}`
        );
        error.statusCode = response.statusCode;
        reject(error);
      },
      fail: reject
    });
  }));
}

function listGarments() {
  return request("/catalog/garments");
}

function listWardrobe() {
  return request("/wardrobe/garments");
}

function getRecentExperience() {
  return request("/me/recent-experience");
}

function createExperience(garmentId) {
  return request("/experience-sessions", {
    method: "POST",
    data: { user_id: "dev-user", garment_id: garmentId }
  });
}

function selectGarment(sessionId, garmentId) {
  return request(`/experience-sessions/${sessionId}/garment`, {
    method: "PUT",
    data: { garment_id: garmentId }
  });
}

function generateStatic(sessionId, personImageId = null) {
  return request(`/experience-sessions/${sessionId}/static-tryon`, {
    method: "POST",
    data: personImageId ? { person_image_id: personImageId } : {}
  });
}

function getFitAnalysis(garmentId) {
  return request(`/catalog/garments/${garmentId}/fit-analysis`);
}

function deleteFitProfile() {
  return request("/me/fit-profile", { method: "DELETE" });
}

function getMyFitProfile() {
  return request("/me/fit-profile");
}

function getMyUsage() {
  return request("/me/usage");
}

function createRealtime(sessionId) {
  return request(`/experience-sessions/${sessionId}/realtime`, { method: "POST" });
}

function createBodyScan(sessionId) {
  return request("/body-scans", {
    method: "POST",
    data: { experience_session_id: sessionId, consented: true }
  });
}

function uploadBodyScanFrame(scanId, angle, filePath) {
  const app = getApp();
  const ready = app.globalData.authReady || Promise.resolve();
  return ready.catch(() => null).then(() => new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${app.globalData.apiBaseUrl}/body-scans/${scanId}/frames`,
      filePath,
      name: "image",
      formData: { angle },
      header: app.globalData.accessToken
        ? { Authorization: `Bearer ${app.globalData.accessToken}` }
        : {},
      timeout: 15000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          try {
            resolve(JSON.parse(response.data));
          } catch (error) {
            reject(error);
          }
          return;
        }
        reject(new Error(`UPLOAD ${response.statusCode}`));
      },
      fail: reject
    });
  }));
}

function completeBodyScan(scanId) {
  return request(`/body-scans/${scanId}/complete`, { method: "POST" });
}

function uploadGarment(filePath, name, category = "tops") {
  const app = getApp();
  const ready = app.globalData.authReady || Promise.resolve();
  return ready.catch(() => null).then(() => new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${app.globalData.apiBaseUrl}/wardrobe/garments`,
      filePath,
      name: "image",
      formData: {
        user_id: "dev-user",
        name,
        category
      },
      timeout: 15000,
      header: app.globalData.accessToken
        ? { Authorization: `Bearer ${app.globalData.accessToken}` }
        : {},
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          try {
            resolve(JSON.parse(response.data));
          } catch (error) {
            reject(error);
          }
          return;
        }
        reject(new Error(`UPLOAD ${response.statusCode}`));
      },
      fail: reject
    });
  }));
}

function uploadPersonImage(filePath) {
  const app = getApp();
  const ready = app.globalData.authReady || Promise.resolve();
  return ready.catch(() => null).then(() => new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${app.globalData.apiBaseUrl}/person-images`,
      filePath,
      name: "image",
      formData: { user_id: "dev-user" },
      timeout: 15000,
      header: app.globalData.accessToken
        ? { Authorization: `Bearer ${app.globalData.accessToken}` }
        : {},
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          try {
            resolve(JSON.parse(response.data));
          } catch (error) {
            reject(error);
          }
          return;
        }
        reject(new Error(`UPLOAD ${response.statusCode}`));
      },
      fail: reject
    });
  }));
}

function mediaUrl(relativePath) {
  const app = getApp();
  return `${app.globalData.apiBaseUrl}/media/${relativePath}`;
}

function resultUrl(apiPath) {
  if (!apiPath) return "";
  const app = getApp();
  return `${app.globalData.apiBaseUrl.replace(/\/api\/v1$/, "")}${apiPath}`;
}

function deleteMyData() {
  return request("/me/data", {
    method: "DELETE",
    data: { confirmation: "DELETE" }
  });
}

module.exports = {
  createExperience,
  createBodyScan,
  completeBodyScan,
  createRealtime,
  deleteFitProfile,
  deleteMyData,
  generateStatic,
  getFitAnalysis,
  getMyFitProfile,
  getMyUsage,
  getRecentExperience,
  listGarments,
  listWardrobe,
  mediaUrl,
  resultUrl,
  uploadGarment,
  uploadBodyScanFrame,
  uploadPersonImage,
  selectGarment
};
