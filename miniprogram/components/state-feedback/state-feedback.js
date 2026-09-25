// state-feedback — 通用状态反馈：横幅（不打断流程）或块状（空态/错误态）。
// 文案约定：说明发生了什么、内容是否保留、下一步能做什么。
Component({
  properties: {
    kind: { type: String, value: 'block' },        // block | banner
    tone: { type: String, value: 'info' },         // info | warn | error
    title: { type: String, value: '' },
    desc: { type: String, value: '' },
    actionText: { type: String, value: '' },
    secondaryText: { type: String, value: '' },
    closable: { type: Boolean, value: false }
  },

  data: {
    iconText: 'i'
  },

  observers: {
    tone(tone) {
      this.setData({ iconText: tone === 'info' ? 'i' : '!' });
    }
  },

  methods: {
    onAction() { this.triggerEvent('action'); },
    onSecondary() { this.triggerEvent('secondary'); },
    onClose() { this.triggerEvent('close'); }
  }
});
