const { getApiBaseUrl } = require("./config");

App({
  onLaunch() {
    this.globalData.authReady = this.login();
  },

  login() {
    let envVersion = "develop";
    try {
      envVersion = wx.getAccountInfoSync().miniProgram.envVersion || "develop";
    } catch (error) {
      envVersion = "develop";
    }

    const exchange = (path, data = {}) => new Promise((resolve, reject) => {
      wx.request({
        url: `${this.globalData.apiBaseUrl}${path}`,
        method: "POST",
        data,
        success: (response) => {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            this.globalData.accessToken = response.data.access_token;
            resolve(response.data);
            return;
          }
          reject(new Error(`AUTH ${response.statusCode}`));
        },
        fail: reject
      });
    });

    if (envVersion === "develop") {
      return exchange("/auth/dev-login");
    }
    return new Promise((resolve, reject) => {
      wx.login({
        success: ({ code }) => exchange("/auth/wechat", { code }).then(resolve).catch(reject),
        fail: reject
      });
    });
  },

  globalData: {
    apiBaseUrl: getApiBaseUrl(),
    accessToken: "",
    authReady: null
  }
});
