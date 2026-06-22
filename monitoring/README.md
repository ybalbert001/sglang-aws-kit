## 可观测说明

### EC2的上搭建可观测
```bash
cd ec2
docker compose up
```
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

### EKS上搭建可观测

> **数据流程： DCGM Exporter → ADOT Collector → Amazon Managed Prometheus → Amazon Managed Grafana**

#### 部署步骤

复用awsome-distributed-ai中的可观测方法, 具体参见[README.md](](https://github.com/awslabs/awsome-distributed-ai/blob/main/4.validation_and_observability/4.prometheus-grafana/eks-managed-observability/README.md))

- Install GPU Operator
```
# Add NVIDIA Helm repository
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Install GPU Operator
helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator \
  --create-namespace \
  --set dcgmExporter.enabled=true

# Verify installation:
kubectl get pods -n gpu-operator
```

- Automated Deployment
```
git clone https://github.com/awslabs/awsome-distributed-ai.git

cd awsome-distributed-ai/4.validation_and_observability/4.prometheus-grafana/eks-managed-observability

./deploy-obs.sh
```

- AMP & AMG 配置
  - AMG中设置Authentication
  [](https://github.com/user-attachments/assets/4274f4e4-39f9-45f4-9c7f-cf8ddf09979e)
  [](https://github.com/user-attachments/assets/57da52da-fcf6-4cba-a496-ed72ff5c3323)
  - AMG中设置Prometheus的数据源
  [](https://github.com/user-attachments/assets/0ef40c48-84fd-4d2c-b3b5-25301b03698a)
  [](https://github.com/user-attachments/assets/e13078b3-4473-4f35-9deb-04bd34795891)
  - AMG中导入Dashboard
  [](https://github.com/user-attachments/assets/f0165568-1182-47cf-86a4-ecb1b7ce0b68)
  [](https://github.com/user-attachments/assets/244749d0-0b6f-4d0f-80a1-6861aba7918e)

DCGM Dashboard参考效果：
[](https://github.com/user-attachments/assets/d9f9c7cb-89be-4a52-a123-2a6d6516ea23)

