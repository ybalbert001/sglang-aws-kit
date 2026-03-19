## 问题

当sagemaker endpoint 部署好LLM后，可以通过litellm挂载上去，但是如果需要以stream方式访问，需要在payload中指定对应的参数 `stream:true`.

通过http客户端可以让http request包含这个参数，但是如果利用了现成的client，比如cherry studio或者claude Code, 并没有开放灵活性让你设置。

另外如果不使用stream方式，sagemaker endpoint存在60s的timeout限制，可能会导致访问失败。

## 解法

**通过litellm的callback 机制，改写http request的参数**

- litellm 的配置文件 config.yaml 
```yaml
litellm_settings:
  callbacks: ["force_stream.force_stream_instance"]

model_list:
  - model_name: bedrock-claude-opus46
    litellm_params:
      model: bedrock/global.anthropic.claude-opus-4-6-v1
      aws_region_name: us-west-2
      drop_params: true
      additional_drop_params:
        - top_p
  - model_name: sagemaker-qwen3-5-9b
    litellm_params:
      model: sagemaker_chat/sglang-Qwen-Qwen3-5-9B-0317-2139
      aws_region_name: us-east-1
      timeout: 120
      stream: true # 不生效
      max_tokens: 8192
      drop_params: true
```


- litellm中的callback定义脚本 - force_stream.py
```python
from litellm.integrations.custom_logger import CustomLogger

class ForceStream(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if "sagemaker" in data.get("model", ""):
            data["stream"] = True
        return data
      
force_stream_instance = ForceStream()
```

- 启动litellm docker container的docker compose配置文件

```yaml
services:
  litellm:
    build:
      context: .
      args:
        target: runtime
    image: docker.litellm.ai/berriai/litellm:main-stable
    #########################################
    restart: always
    ## Uncomment these lines to start proxy with a config.yaml file ##
    volumes:
     - ./config.yaml:/app/config.yaml
     - ./force_stream.py:/app/force_stream.py
    command:
     - "--config=/app/config.yaml"
    ##############################################
    ports:
      - "8080:4000" # Map the container port to the host, change the host port if necessary
    environment:
      DATABASE_URL: "postgresql://llmproxy:dbpassword9090@db:5432/litellm"
      STORE_MODEL_IN_DB: "True" # allows adding models to proxy via UI
    env_file:
      - .env # Load local .env file
    depends_on:
      - db  # Indicates that this service depends on the 'db' service, ensuring 'db' starts first
    healthcheck:  # Defines the health check configuration for the container
      test:
        - CMD-SHELL
        - python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:4000/health/liveliness')"  # Command to execute for health check
      interval: 30s  # Perform health check every 30 seconds
      timeout: 10s   # Health check command times out after 10 seconds
      retries: 3     # Retry up to 3 times if health check fails
      start_period: 40s  # Wait 40 seconds after container start before beginning health checks

  db:
    image: postgres:16
    restart: always
    container_name: litellm_db
    environment:
      POSTGRES_DB: litellm
      POSTGRES_USER: llmproxy
      POSTGRES_PASSWORD: dbpassword9090
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data # Persists Postgres data across container restarts
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d litellm -U llmproxy"]
      interval: 1s
      timeout: 5s
      retries: 10

  prometheus:
    image: prom/prometheus
    volumes:
      - prometheus_data:/prometheus
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.retention.time=15d"
    restart: always

volumes:
  prometheus_data:
    driver: local
  postgres_data:
    name: litellm_postgres_data # Named volume for Postgres data persistence
```