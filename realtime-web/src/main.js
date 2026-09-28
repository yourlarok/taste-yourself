import './style.css';

const output = document.querySelector('#output');
const status = document.querySelector('#live-status');
const veil = document.querySelector('#veil');
const title = document.querySelector('#state-title');
const copy = document.querySelector('#state-copy');
const retry = document.querySelector('#retry');
const garmentsEl = document.querySelector('#garment-rail');
const nameEl = document.querySelector('#garment-name');
const params = new URLSearchParams(location.hash.slice(1));
let bootstrap;
try {
  bootstrap = JSON.parse(params.get('d') || '{}');
} catch (error) {
  bootstrap = {};
}
history.replaceState(null, '', location.pathname);

let client;
let localStream;
let selectedId = bootstrap.selectedGarmentId || '';
let connecting = false;

const SCENE_PROMPTS = {
  beach: 'a bright natural seaside with pale sand, blue water, and realistic coastal daylight',
  city: 'a refined contemporary city street with realistic daylight',
  cafe: 'an elegant warm cafe interior with natural window light',
  garden: 'a lush quiet garden with soft natural daylight',
  studio: 'a minimal premium fashion studio with soft editorial lighting',
  snow: 'a realistic snowy outdoor setting with soft winter daylight',
  sunset: 'an open outdoor setting during a warm natural sunset'
};

function tryonPrompt(garment) {
  const scene = SCENE_PROMPTS[bootstrap.scene];
  const background = scene
    ? `Replace the background with ${scene}, with coherent lighting and perspective.`
    : `Preserve the original background.`;
  return `A person wearing the garment in the reference image: ${garment.name || 'selected garment'}. Preserve the person's identity, body shape, and pose. ${background}`;
}

function message(text, detail, failed = false) {
  title.textContent = text;
  copy.textContent = detail || '';
  veil.classList.remove('is-hidden');
  retry.hidden = !failed;
  status.classList.toggle('is-error', failed);
  status.querySelector('span').textContent = failed ? '未连接' : '连接中';
}

function shutdown() {
  if (client) {
    try { client.disconnect(); } catch (error) { /* already closed */ }
    client = null;
  }
  if (localStream) {
    localStream.getTracks().forEach((track) => track.stop());
    localStream = null;
  }
}

function close() {
  shutdown();
  const bridge = window.wx && window.wx.miniProgram;
  if (bridge) {
    bridge.postMessage({ data: { selectedGarmentId: selectedId } });
    bridge.navigateBack({ delta: 1 });
  } else if (history.length > 1) {
    history.back();
  }
}

function selectedGarment() {
  return (bootstrap.garments || []).find((item) => item.id === selectedId);
}

function renderGarments() {
  const garments = bootstrap.garments || [];
  garmentsEl.replaceChildren();
  garments.forEach((garment) => {
    const button = document.createElement('button');
    button.className = 'garment' + (garment.id === selectedId ? ' is-selected' : '');
    button.type = 'button';
    button.setAttribute('aria-label', garment.name || '选择衣服');
    const image = document.createElement('img');
    image.src = garment.image_url;
    image.alt = '';
    button.append(image);
    button.addEventListener('click', () => setGarment(garment));
    garmentsEl.append(button);
  });
  const current = selectedGarment();
  nameEl.textContent = current ? current.name : '实时试衣镜';
}

async function setGarment(garment) {
  selectedId = garment.id;
  renderGarments();
  if (!client) return;
  try {
    await client.set({ image: garment.image_url, prompt: tryonPrompt(garment) });
  } catch (error) {
    message('衣服切换失败', '实时连接已保留，请重试切换或结束本次试穿。', true);
  }
}

async function connect() {
  if (connecting) return;
  connecting = true;
  retry.hidden = true;
  message('正在连接实时试衣镜', '请保持页面开启，影像会在相机进行中实时返回。');
  try {
    if (!bootstrap.apiKey || !bootstrap.garments || !selectedGarment()) {
      throw new Error('试衣凭证或所选衣服缺失，请返回试衣空间后重试。');
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('当前微信版本不支持在内嵌页面开启实时相机。');
    }
    message('正在载入实时试衣', '正在建立实时影像链路，请稍候。');
    const { createDecartClient, models } = await import('@decartai/sdk');
    const model = models.realtime('lucy-vton-latest');
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: 'user',
        width: model.width,
        height: model.height,
        frameRate: model.fps
      }
    });
    const garment = selectedGarment();
    const decart = createDecartClient({ apiKey: bootstrap.apiKey });
    client = await decart.realtime.connect(localStream, {
      model,
      mirror: 'auto',
      onRemoteStream: (stream) => {
        output.srcObject = stream;
        output.play().catch(() => {});
        veil.classList.add('is-hidden');
      },
      initialState: {
        image: garment.image_url,
        prompt: { text: tryonPrompt(garment), enhance: false }
      }
    });
    client.on('connectionChange', (state) => {
      if (state === 'connected' || state === 'generating') {
        status.classList.remove('is-error');
        status.querySelector('span').textContent = '实时中';
      } else if (state === 'disconnected') {
        message('实时连接已断开', '没有切换到录像或演示画面。请重新连接。', true);
      }
    });
    client.on('error', () => message('实时试衣连接失败', '请检查网络、相机权限或 Decart 实时服务状态。', true));
  } catch (error) {
    if (localStream) {
      localStream.getTracks().forEach((track) => track.stop());
      localStream = null;
    }
    message('暂时无法开启实时试衣', error && error.message ? error.message : '请检查网络和相机权限后重试。', true);
  } finally {
    connecting = false;
  }
}

document.querySelector('#back').addEventListener('click', close);
document.querySelector('#exit').addEventListener('click', close);
retry.addEventListener('click', connect);
renderGarments();
connect();

window.addEventListener('pagehide', shutdown);

document.addEventListener('visibilitychange', () => {
  if (document.hidden && (client || localStream)) {
    if (client) client.disconnect();
    client = null;
    if (localStream) localStream.getTracks().forEach((track) => track.stop());
    localStream = null;
    message('实时试穿已暂停', '为保护隐私，页面离开前台后相机与连接均已关闭。', true);
  }
});
