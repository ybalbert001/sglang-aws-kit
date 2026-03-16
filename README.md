# SGLang AWS Kit

SGLang 在 AWS 上的配套工具集，包含 SageMaker Endpoint 部署方案、Prometheus + Grafana 监控栈，以及 Anthropic API 兼容性修复补丁。

## 项目结构

```
sglang-aws-kit/
├── sagemaker_endpoint_deploy/   # SGLang 部署到 SageMaker Endpoint
├── monitoring/                  # Prometheus + Grafana 监控服务
└── sglang_thinking_usage_fix.patch  # Anthropic API 兼容性修复补丁
```

## 组件说明

### 1. SageMaker Endpoint 部署 (`sagemaker_endpoint_deploy/`)

利用 SGLang v0.2.13+ 原生的 SageMaker API 支持（`/ping` 和 `/invocations` 端点），将 LLM 模型部署为 SageMaker 实时推理端点。

**特性：**
- 直接使用 SGLang 内置的 SageMaker 接口，无需代理层
- 支持 Chat Completions API（流式 / 非流式）
- 通过 s5cmd 从 S3 高速下载模型

**快速开始：**
1. 在 SageMaker Notebook 中打开 `deploy_and_test.ipynb`
2. 配置模型参数（模型 ID、实例类型、SGLang 版本）
3. 构建 Docker 镜像并推送到 ECR
4. 下载模型上传至 S3，部署 SageMaker 端点

详见 [sagemaker_endpoint_deploy/README.md](sagemaker_endpoint_deploy/README.md)。

### 2. 监控服务 (`monitoring/`)

基于 Docker Compose 的一键监控方案，包含 Prometheus 指标采集和 Grafana 可视化看板。

**包含组件：**
- **Prometheus**：采集 SGLang 服务器指标（默认抓取 `127.0.0.1:30000`）及 DCGM GPU 指标
- **Grafana**：预配置数据源和仪表盘，支持匿名访问
  - SGLang 推理服务监控面板（v1 / v2）
  - DCGM GPU 监控面板

**快速开始：**
```bash
# 1. 启动 SGLang 服务（需开启 metrics）
python -m sglang.launch_server --model-path <model> --port 30000 --enable-metrics

# 2. 启动监控栈
cd monitoring
docker compose up
```

- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

详见 [monitoring/README.md](monitoring/README.md)。

### 3. Anthropic API 兼容性修复 (`sglang_thinking_usage_fix.patch`)

针对 SGLang Anthropic API 端点的修复补丁，解决以下问题：

- **Thinking Block 缺失**：将 `reasoning_content` 映射为 Anthropic 格式的 `thinking` content block
- **Usage 信息不完整**：补全流式和非流式响应中的 `cache_read_input_tokens` 字段
- **字段默认值修正**：`cache_creation_input_tokens` 和 `cache_read_input_tokens` 默认值从 `None` 改为 `0`
- **Thinking 配置支持**：新增 `AnthropicThinking` 模型，支持 `thinking` 请求参数

**使用方式：**
```bash
# 在 SGLang 源码目录下应用补丁
cd /path/to/sglang
git apply /path/to/sglang_thinking_usage_fix.patch
```

## License

[MIT](LICENSE)
