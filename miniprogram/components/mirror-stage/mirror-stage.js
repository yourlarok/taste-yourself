// mirror-stage — 首页主舞台：整块区域可点击进入镜前。
// mode = recent：展示最近一次试穿结果图、衣服名称、时间与“继续上次试穿”；
// mode = empty ：三步微文案沿镜面边缘纵向排布 + 真实演示衣服缩略图。
Component({
  properties: {
    mode: { type: String, value: 'empty' },        // empty | recent
    garmentName: { type: String, value: '' },
    updatedText: { type: String, value: '' },
    resultImage: { type: String, value: '' },
    demoName: { type: String, value: '' },
    demoImage: { type: String, value: '' },
    hintText: { type: String, value: '开始第一次试穿' }
  },

  methods: {
    onEnter() {
      this.triggerEvent('enter');
    },
    onChange() {
      this.triggerEvent('change');
    }
  }
});
