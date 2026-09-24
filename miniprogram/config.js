const API_BASE_URLS = {
  develop: "http://127.0.0.1:8000/api/v1",
  trial: "https://api.example.com/api/v1",
  release: "https://api.example.com/api/v1"
};

function getApiBaseUrl() {
  try {
    const account = wx.getAccountInfoSync();
    const envVersion = account.miniProgram.envVersion || "develop";
    return API_BASE_URLS[envVersion];
  } catch (error) {
    return API_BASE_URLS.develop;
  }
}

module.exports = { API_BASE_URLS, getApiBaseUrl };
