Component({
  properties: {
    steps: { type: Array, value: [] },
    current: { type: Number, value: 0 },
    detail: { type: String, value: '' }
  },

  data: {
    viewSteps: []
  },

  observers: {
    'steps,current': function buildViewSteps(steps, current) {
      const active = Number(current) || 0;
      this.setData({
        viewSteps: (steps || []).map((step, index) => ({
          key: step.key || String(index),
          label: step.label || '',
          indexText: index < 9 ? '0' + (index + 1) : String(index + 1),
          state: index < active ? 'done' : index === active ? 'current' : 'waiting'
        }))
      });
    }
  }
});
