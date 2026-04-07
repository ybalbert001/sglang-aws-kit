# SGLang AWS Kit

SGLang 在 AWS 上的配套工具集，包含 SageMaker Endpoint 部署方案、Prometheus + Grafana 监控栈、LiteLLM 代理定制 Hook，以及 Anthropic API 兼容性修复补丁。

## 项目结构

```
sglang-aws-kit/
├── sagemaker_endpoint_deploy/   # SGLang 部署到 SageMaker Endpoint
├── monitoring/                  # Prometheus + Grafana 监控服务
├── customerize_litellm/         # LiteLLM 代理配置与 Anthropic Schema 修复 Hook
├── faq/                         # 常见问题解答
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

### 3. LiteLLM 代理定制 (`customerize_litellm/`)

通过自定义 LiteLLM Hook，可以对litellm的request 和 response进行定制性的处理。

**解决的问题：**

1. SageMaker Endpoint 的响应格式与标准 Anthropic API 不完全兼容，导致 LiteLLM 无法正确解析流式响应。`stream_anthropic_schema_fixer.py` 作为 LiteLLM 的 callback hook，在响应返回前进行格式修正。
2. 有些任务可以分发到不同的模型来处理，以节约成本。dynamic_tagging_handler.py 构建了一个hook，用于通过message的动态分发任务。代码中的例子是用于区分Claude Code的主线任务和支线任务。

**包含文件：**
- `stream_anthropic_schema_fixer.py`：Anthropic Schema 修复 Hook，注册为 LiteLLM callback
- `dynamic_tagging_handler.py`: 区分ClaudeCode的主线任务和支线任务，把支线任务分发给开源模型。
- `config.yaml`：LiteLLM 代理配置，启用 hook 并配置 SageMaker 模型
- `docker-compose.yml`：一键启动 LiteLLM 代理（含 PostgreSQL + Prometheus）

**快速开始：**
```bash
cd customerize_litellm
# 配置 config.yaml 中的模型名称和 AWS Region
# 配置 .env 文件中的 AWS 凭证
docker compose up
```

- LiteLLM Proxy: http://localhost:8080

## License

[MIT](LICENSE)
