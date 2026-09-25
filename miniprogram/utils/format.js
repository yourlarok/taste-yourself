// utils/format.js — 展示层格式化工具
function relativeTime(ts) {
  if (!ts) return '';
  const diff = Date.now() - Number(ts);
  const min = 60 * 1000;
  const hour = 60 * min;
  const day = 24 * hour;
  if (diff < min) return '刚刚';
  if (diff < hour) return Math.floor(diff / min) + ' 分钟前';
  if (diff < day) return Math.floor(diff / hour) + ' 小时前';
  if (diff < 2 * day) return '昨天';
  if (diff < 30 * day) return Math.floor(diff / day) + ' 天前';
  const d = new Date(Number(ts));
  return (d.getMonth() + 1) + '月' + d.getDate() + '日';
}

function pad2(n) {
  return n < 10 ? '0' + n : '' + n;
}

module.exports = { relativeTime, pad2 };
