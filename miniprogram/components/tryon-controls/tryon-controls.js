// tryon-controls — 镜前底部操作层。
// “生成试穿照”是唯一主操作；“尺码差异”“动态试衣 · 15 秒”为视觉权重更低的二级入口；
// 动态进行中切换为倒计时上下文，可提前结束。
Component({
  properties: {
    phase: { type: String, value: 'camera' },      // camera | capturing | generating | result
    garmentName: { type: String, value: '' },
    generateDisabled: { type: Boolean, value: false },
    disabledHint: { type: String, value: '' },      // 例如额度用完的说明
    generatingText: { type: String, value: '正在生成…' },
    realtimeState: { type: String, value: 'idle' } // idle | connecting | active | ending
  },

  data: {
    mainText: '生成试穿照',
    busy: false,
    realtimeUi: false
  },

  observers: {
    'phase, garmentName': function (phase, garmentName) {
      let text = '生成试穿照';
      if (phase === 'result') text = '重新生成试穿照';
      else if (garmentName) text = '生成试穿照 · ' + garmentName;
      this.setData({
        mainText: text,
        busy: phase === 'capturing' || phase === 'generating'
      });
    },
    realtimeState(state) {
      this.setData({ realtimeUi: state === 'connecting' || state === 'active' || state === 'ending' });
    }
  },

  methods: {
    onGenerate() {
      if (this.data.busy || this.data.generateDisabled) return; // 生成中防重复提交
      this.triggerEvent('generate');
    },
    onOpenFit() {
      if (!this.data.busy) this.triggerEvent('open-fit');
    },
    onStartRealtime() {
      // 动态试衣与静态试穿额度相互独立，仅生成中不可进入
      if (!this.data.busy) this.triggerEvent('start-realtime');
    },
    onEndRealtime() {
      this.triggerEvent('end-realtime');
    }
  }
});
