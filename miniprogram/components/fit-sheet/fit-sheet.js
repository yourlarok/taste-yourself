// fit-sheet — 尺码差异底部抽屉。
// 原则：只分析，不打分、不排序、不推荐；按商品原始尺码顺序展示；
// 不用绿色/红色表达“正确/错误”，颜色仅用于信息层级。
Component({
  properties: {
    visible: { type: Boolean, value: false },
    state: { type: String, value: 'idle' },   // idle | profile_required | loading | ready | missing_product_data | error
    rows: { type: Array, value: [] },          // 已由页面计算好可视化参数的尺码行
    sourceText: { type: String, value: '' },   // 数据来源与测量误差
    errorTitle: { type: String, value: '' },
    errorDesc: { type: String, value: '' },
    garmentName: { type: String, value: '' },
    canEditSizeChart: { type: Boolean, value: false }
  },

  data: {
    expandedIndex: -1,
    sourceOpen: false
  },

  observers: {
    visible(v) {
      if (!v) this.setData({ expandedIndex: -1, sourceOpen: false });
    }
  },

  methods: {
    onMaskTap() { this.triggerEvent('close'); },
    onClose() { this.triggerEvent('close'); },
    onStartScan() { this.triggerEvent('start-scan'); },
    onSkip() { this.triggerEvent('skip'); },
    onRetry() { this.triggerEvent('retry'); },
    onEditSizeChart() { this.triggerEvent('edit-size-chart'); },
    noop() {},

    onToggleRow(e) {
      const index = e.currentTarget.dataset.index;
      this.setData({ expandedIndex: this.data.expandedIndex === index ? -1 : index });
    },

    onToggleSource() {
      this.setData({ sourceOpen: !this.data.sourceOpen });
    }
  }
});
