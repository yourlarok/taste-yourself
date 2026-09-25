let rowSequence = 0;

function emptyRow() {
  rowSequence += 1;
  return { uid: rowSequence, size: '', chest_cm: '', waist_cm: '', hip_cm: '', shoulder_cm: '', length_cm: '' };
}

Component({
  properties: {
    visible: { type: Boolean, value: false },
    garmentName: { type: String, value: '' },
    saving: { type: Boolean, value: false }
  },

  data: {
    brand: '',
    metrics: [
      { key: 'chest_cm', label: '胸围' },
      { key: 'waist_cm', label: '腰围' },
      { key: 'hip_cm', label: '臀围' },
      { key: 'shoulder_cm', label: '肩宽' },
      { key: 'length_cm', label: '衣长' }
    ],
    rows: [emptyRow()]
  },

  observers: {
    visible(value) {
      if (value) this.setData({ brand: '', rows: [emptyRow()] });
    }
  },

  methods: {
    noop() {},
    onClose() { this.triggerEvent('close'); },
    onBrandInput(e) { this.setData({ brand: e.detail.value }); },
    onCellInput(e) {
      const index = Number(e.currentTarget.dataset.index);
      const field = e.currentTarget.dataset.field;
      this.setData({ ['rows[' + index + '].' + field]: e.detail.value });
    },
    onAddRow() {
      if (this.data.rows.length >= 12) {
        wx.showToast({ title: '一次最多录入 12 个尺码', icon: 'none' });
        return;
      }
      this.setData({ rows: this.data.rows.concat([emptyRow()]) });
    },
    onRemoveRow(e) {
      if (this.data.rows.length === 1) return;
      const index = Number(e.currentTarget.dataset.index);
      this.setData({ rows: this.data.rows.filter((_, i) => i !== index) });
    },
    onSubmit() {
      const variants = [];
      for (let index = 0; index < this.data.rows.length; index += 1) {
        const row = this.data.rows[index];
        const label = String(row.size || '').trim();
        if (!label) {
          wx.showToast({ title: '请填写每行尺码', icon: 'none' });
          return;
        }
        const measurements = {};
        ['chest_cm', 'waist_cm', 'hip_cm', 'shoulder_cm', 'length_cm'].forEach((key) => {
          const value = Number(row[key]);
          if (Number.isFinite(value) && value > 0) measurements[key] = value;
        });
        if (!Object.keys(measurements).length) {
          wx.showToast({ title: label + ' 至少填写一项尺寸', icon: 'none' });
          return;
        }
        variants.push({
          sku_id: 'manual-' + index + '-' + label,
          size_label: label,
          measurements_cm: measurements
        });
      }
      this.triggerEvent('submit', {
        brand: String(this.data.brand || '').trim() || null,
        stretch_percent: 0,
        variants
      });
    }
  }
});
