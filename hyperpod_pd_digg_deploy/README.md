# SGLang PD Disaggregation Deploy

SGLang Prefill-Decode 分离架构部署配置，支持两种部署方式。

## 1. EKS / HyperPod 部署

基于 Kubernetes StatefulSet 部署 Prefill 和 Decode 节点，通过 NIXL (EFA libfabric) 传输 KV-Cache。

相关文件：
- `sgl059-pd-kimi-k2.5-slgcu13dev-with-monitoring-v5.yaml` — Kimi-K2.5 完整部署（含 Router、Prometheus、AMP remote write）
- `sgl059-pd-mimo-v2-flash-slgcu13dev-with-monitoring.yaml` — MiMo-V2-Flash 完整部署
- `dcgm_metric_exporter.yaml` — GPU 指标采集 DaemonSet
- `download-model-daemonset.yaml` — 模型预下载到节点 NVMe
- `build-image.sh` — 构建 SGLang 镜像并推送 ECR
- `mooncake/` — 基于 Mooncake Transfer Engine 的替代传输方案

部署：
```bash
kubectl apply -f sgl059-pd-kimi-k2.5-slgcu13dev-with-monitoring-v5.yaml
kubectl apply -f dcgm_metric_exporter.yaml
```

## 2. EC2 Docker 部署

单节点 docker-compose 方式，在一台 8 GPU 机器上运行 PD 分离（6 Prefill + 2 Decode）。

相关文件：
- `single_node_pd_digg_deploy/docker-compose-pd-b300.yaml` — Qwen3.5-122B-A10B-FP8 单机部署

部署：
```bash
cd single_node_pd_digg_deploy
docker compose -f docker-compose-pd-b300.yaml up -d
```
