# FASHN VTON GPU Worker

独立部署的静态试穿推理服务。业务 API 不加载模型，只通过内网调用该 Worker。

模型选择为 FASHN VTON v1.5：代码和模型发布为 Apache-2.0，支持 `tops`、`bottoms`、`one-pieces`。上游仓库及其第三方组件的许可证仍需在部署前逐项复核并保留声明。

## GPU 条件

官方权重约 2GB；Ampere 及更新 GPU 使用 BF16。更老的 GPU/CPU 会转为 FP32，因此当前这台 8GB RTX 2080 只适合接口开发，不作为可承诺的生产推理机器。建议首个内测环境使用至少 16GB 显存的 Ampere 或更新 GPU，并以真实峰值显存测试为准。

## 部署

先从上游仓库下载权重到宿主机目录：

```bash
git clone https://github.com/fashn-AI/fashn-vton-1.5.git
cd fashn-vton-1.5
python scripts/download_weights.py --weights-dir ./weights
```

构建并运行 Worker：

```bash
docker build -t taste-yourself-fashn-worker workers/fashn_vton
docker run --gpus all --rm -p 9000:9000 \
  -e FASHN_WEIGHTS_DIR=/weights \
  -e FASHN_WORKER_TOKEN=replace-with-a-long-random-token \
  -v /absolute/path/to/weights:/weights:ro \
  -v /absolute/path/to/outputs:/worker/outputs \
  taste-yourself-fashn-worker
```

Worker 只应暴露在业务后端可访问的私有网络中。生产环境必须设置 `FASHN_WORKER_TOKEN`，并限制请求体大小、并发数和网络访问控制。
