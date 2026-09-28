// tryon-controls — 镜前底部操作层。
// “生成试穿照”是唯一主操作（快门语义，主标题 + 当前衣服副标题）；
// “尺码差异”“实时试衣镜”为视觉权重更低的二级入口。
Component({
  properties: {
    phase: { type: String, value: 'camera' },      // camera | capturing | generating | result
    garmentName: { type: String, value: '' },
    generateDisabled: { type: Boolean, value: false },
    disabledHint: { type: String, value: '' },      // 例如额度用完的说明
    generatingText: { type: String, value: '正在生成…' },
    realtimeState: { type: String, value: 'idle' }
  },

  data: {
    mainText: '生成试穿照',
    subText: '',
    busy: false,
  },

  observers: {
    'phase, garmentName': function (phase, garmentName) {
      this.setData({
        mainText: phase === 'result' ? '重新生成试穿照' : '生成试穿照',
        subText: garmentName || '先在下方选择一件衣服',
        busy: phase === 'capturing' || phase === 'generating'
      });
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
    }
  }
});
