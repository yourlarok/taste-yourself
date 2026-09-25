// garment-strip — 横向衣服轨道：示例衣服 + 我的衣橱，真实缩略图与名称；
// 末尾“添加衣服”；上传中 / 上传失败 / 审核拒绝 / 图片失效均为独立状态。
Component({
  properties: {
    catalog: { type: Array, value: [] },
    wardrobe: { type: Array, value: [] },
    selectedId: { type: String, value: '' },
    uploading: { type: Boolean, value: false },
    uploadPercent: { type: Number, value: 0 },
    uploadError: { type: String, value: '' }        // '' | 'failed' | 'rejected'
  },

  data: {
    catalogView: [],
    wardrobeView: []
  },

  observers: {
    catalog(list) {
      this.setData({ catalogView: this.decorate(list) });
    },
    wardrobe(list) {
      this.setData({ wardrobeView: this.decorate(list) });
    }
  },

  methods: {
    decorate(list) {
      const broken = this.data.brokenImages || {};
      return (list || []).map((g) => ({
        id: g.id,
        name: g.name,
        image: g.image_url,
        broken: !!broken[g.id]
      }));
    },

    onSelect(e) {
      const { id } = e.currentTarget.dataset;
      if (id && id !== this.data.selectedId) {
        this.triggerEvent('select', { id });
      }
    },

    onAdd() {
      if (!this.data.uploading) this.triggerEvent('add');
    },

    onRetry() {
      this.triggerEvent('retry-upload');
    },

    onImageError(e) {
      const { id } = e.currentTarget.dataset;
      const broken = Object.assign({}, this.data.brokenImages || {}, { [id]: true });
      this.setData({
        brokenImages: broken,
        catalogView: this.decorate(this.data.catalog),
        wardrobeView: this.decorate(this.data.wardrobe)
      });
    }
  }
});
