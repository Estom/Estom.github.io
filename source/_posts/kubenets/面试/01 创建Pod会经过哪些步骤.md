---
title: "01 创建Pod会经过哪些步骤"
date: 1766125929
updated: 1766125929
tags: []
categories:
  - "kubenets"
---

在 Kubernetes（简称 K8s）集群中，直接执行 `kubectl apply -f pod.yaml` 来部署一个 Pod 时，会触发集群的一系列自动化流程。这是一个典型的声明式操作，用户只需描述 Pod 的期望状态（通过 YAML 文件），K8s 控制平面和节点组件会协同工作，将其转化为实际运行状态。整个过程体现了 K8s 的核心原理：声明式 API、期望状态驱动（Desired State vs. Actual State）、组件间松耦合协作（通过 API Server 和 etcd 实现状态同步），以及自愈机制（如重试和健康检查）。下面，我结合 K8s 原理，从请求提交到 Pod 运行就绪，逐阶段详细拆解整个流程。

### 阶段 1：用户请求提交与 API Server 处理
用户通过 `kubectl apply` 命令提交 Pod 的 YAML 配置（包含 metadata 如名称、命名空间；spec 如容器镜像、资源需求、端口等）。`kubectl` 会解析 YAML，确保它符合 K8s 的 Pod 资源规范（v1 Pod API），然后转换为 JSON 格式的 HTTP 请求发送到 K8s API Server。这体现了 K8s 的 RESTful API 设计，所有资源操作（如创建、更新）都通过 API Server 统一入口。

- **认证与授权**：
  - API Server 首先进行认证（Authentication）：验证请求者的身份，使用 kubeconfig 中的证书、Bearer Token 或其他机制（如 Service Account）。如果认证失败，请求将被拒绝（返回 401 Unauthorized）。
  - 接着是授权（Authorization）：基于 Role-Based Access Control (RBAC) 检查用户是否有权限在指定命名空间创建 Pod（需要 `pods/create` 权限）。如果没有权限，返回 403 Forbidden。这确保了集群的安全性和多租户隔离。

- **准入控制（Admission Control）**：
  - 通过认证授权后，API Server 调用一组准入控制器（Admission Controllers），这些是可插拔的 webhook 或内置插件，用于在资源持久化前校验和修改配置。
    - **校验（Validating）**：检查 Pod spec 的合法性，例如容器镜像是否有效、资源请求（如 CPU/Memory）是否为正值、端口是否冲突等。如果违反规范（如使用无效的镜像标签），请求将被拒绝。
    - **修改（Mutating）**：自动填充默认值，例如如果未指定 `restartPolicy`，默认为 `Always`；或添加默认的 SecurityContext（如非 root 用户运行）。
    - **高级准入**：如果集群启用了 PodSecurityAdmission（PSA）或旧的 PodSecurityPolicy (PSP)，会强制安全约束，如禁止特权容器或主机路径挂载。这体现了 K8s 的安全第一原理，防止恶意或不安全的配置进入集群。

- **持久化到 etcd**：
  - 所有准入通过后，API Server 将 Pod 对象（包括 metadata、spec 和初始 status 为 Pending）写入 etcd（K8s 的分布式键值存储，集群的单一真相来源）。同时生成 `metadata.resourceVersion` 用于乐观并发控制（避免并发修改冲突）。etcd 的 Watch 机制会通知其他组件（如 Scheduler）这个新 Pod 的存在。这一步标志着 Pod 被 “创建”，但还未调度或运行。

如果 YAML 中已存在同名 Pod，`apply` 会计算差异（基于 strategic merge patch），仅更新变更部分，而非覆盖整个对象。这体现了声明式的幂等性：多次 apply 相同的 YAML 不会导致意外行为。

### 阶段 2：Scheduler 调度 Pod 到目标节点
Pod 写入 etcd 后，Scheduler（调度器，一个独立的控制平面组件）通过 Watch API Server 感知到这个未调度 Pod（`spec.nodeName` 为空），启动调度循环。Scheduler 的核心原理是谓词（Predicate）和优先级（Priority）机制，确保 Pod 被分配到最合适的节点，实现资源利用最大化和高可用。

- **筛选候选节点（Filter/Predicate）**：
  - 从集群所有节点（通过 Node 对象列表）中过滤出可行节点。规则包括：
    - **资源匹配**：检查节点剩余资源（从 Node status.allocatable 减去已分配）是否满足 Pod 的 `spec.resources.requests` 和 `limits`。例如，如果 Pod 请求 2Gi 内存，节点剩余不足则排除。
    - **亲和性与反亲和性**：Pod 的 `nodeAffinity` 或 `podAffinity` 要求节点/其他 Pod 的标签匹配（如 `nodeSelector: {env: prod}`），否则排除。
    - **污点与容忍（Taints & Tolerations）**：节点可能有 Taint（如 `NoSchedule`），Pod 必须声明 `tolerations` 来容忍，否则无法调度。
    - **其他约束**：如卷亲和性（Pod 的 PV 必须在节点可用）、主机端口（`hostPort`）是否已被占用、节点状态（Ready）等。如果无节点匹配，Pod 保持 Pending，事件日志会记录原因（如 "0/5 nodes are available: 2 Insufficient cpu"）。

- **节点打分（Score/Priority）**：
  - 对过滤后的节点，按优先级函数打分（0-10 分，乘以权重后总分 0-100）。默认函数包括：
    - **资源均衡**：LeastRequestedPriority（优先低负载节点）和 BalancedResourceAllocation（均衡 CPU/内存使用）。
    - **亲和性加分**：如 Pod 与现有 Pod 在同一拓扑域（zone/rack）加分，提高容灾或降低延迟。
    - **自定义扩展**：集群可配置插件或 extender webhook 来添加规则（如优先 SSD 节点）。
  - 选择最高分节点，如果平分则随机选一。

- **绑定节点（Bind）**：
  - Scheduler 通过 API Server 更新 Pod 对象：设置 `spec.nodeName` 为目标节点，并添加绑定事件。更新写入 etcd，Pod status 变为 Scheduled。这体现了异步协作：Scheduler 不直接操作节点，而是通过 etcd 通知 Kubelet。

如果集群节点不足或约束太严，调度可能失败，Pod 无限 Pending，用户需通过 `kubectl describe pod` 查看事件。

### 阶段 3：目标节点的 Kubelet 创建并运行 Pod
节点上的 Kubelet（每个节点运行的代理组件）通过 Watch 机制发现分配给自己的 Pod（匹配 `spec.nodeName`），开始本地执行。Kubelet 的原理是调和循环（Reconcile Loop）：不断比较 Pod 的期望状态与实际状态，并采取行动实现一致性。

- **PodSpec 解析与准备**：
  - Kubelet 从 API Server 获取完整 Pod 配置，进行本地校验（如确认节点资源足够）。如果不符，会报告事件并拒绝。

- **容器运行时交互（CRI）**：
  - Kubelet 通过 Container Runtime Interface (CRI) 与底层运行时（如 Docker、containerd）通信：
    - **镜像拉取**：根据 `spec.containers[*].image` 从仓库拉取镜像（使用 ImagePullSecrets 如果需要认证）。如果失败（如网络问题），状态变为 ImagePullBackOff，重试指数退避。
    - **卷准备**：创建并挂载 volumes，如 EmptyDir（临时目录）、ConfigMap/Secret（注入配置）、PersistentVolume (PV)（通过 CSI 驱动绑定持久存储）。
    - **网络配置**：调用 Container Network Interface (CNI) 插件（如 Flannel、Calico）分配 Pod IP，设置 veth 接口和路由，确保 Pod 网络连通（符合 K8s 的网络模型：所有 Pod 可互相访问，无 NAT）。

- **启动容器**：
  - 先运行 `initContainers`（顺序执行初始化，如数据准备），成功后启动主容器。
  - 应用 `securityContext`（如 runAsUser、capabilities），注入环境变量（envFrom）、命令（command/args）。
  - 如果 `hostNetwork: true`，Pod 共享节点网络命名空间。

- **健康检查与状态报告**：
  - **探针（Probes）**：执行 Startup/Liveness/Readiness Probe（如 exec、httpGet、tcpSocket）。Liveness 失败则重启容器（根据 `restartPolicy`：Always/OnFailure/Never）；Readiness 失败则从 Service Endpoints 移除 Pod IP。
  - Kubelet 每 10 秒（默认）同步 Pod status 到 API Server（写入 etcd），包括条件如 PodScheduled、ContainersReady。用户看到 status 从 Pending -> ContainerCreating -> Running。

如果容器崩溃，Kubelet 自愈：重启并记录日志（`kubectl logs` 查看）。

### 阶段 4：网络与服务就绪（Kube-proxy 参与）
Pod Running 后，如果有匹配的 Service（通过 labels selector），Kube-proxy（节点组件）Watch 到 Pod IP 变化，更新本地转发规则：
- 使用 iptables 或 IPVS 将 Service 的 ClusterIP（VIP）流量负载均衡到 Pod IP:Port。
- 如果是 NodePort/LoadBalancer，配置外部访问。

这实现了服务发现和负载均衡的解耦：Pod 可动态变化，Service 提供稳定入口。

### 特殊情况与自愈
- **失败处理**：如镜像不存在（ErrImagePull）、资源不足（FailedScheduling），K8s 会记录事件并重试。CrashLoopBackOff 表示反复崩溃，需用户干预。
- **更新与删除**：后续 apply 修改 YAML，会触发类似流程，但仅更新差异（RollingUpdate 如果是多副本，但单 Pod 无此）。
- **观测性**：所有步骤生成事件（`kubectl get events`），日志和指标（通过 Metrics Server）便于调试。

### 总结：K8s 核心原理体现
直接 apply Pod YAML 体现了 K8s 的声明式范式：用户声明期望，系统自动调和实际状态。通过 API Server 的中心化、etcd 的持久化和组件的 Watch/Informers 机制，确保分布式一致性。这比 imperative 命令（如 docker run）更具可扩展性和可靠性，支持大规模自动化运维。如果 Pod 是 Deployment/ReplicaSet 的一部分，流程类似但 Controller Manager 会介入管理副本。实际操作中，推荐使用更高层抽象（如 Deployment）而非裸 Pod，以获得内置滚动更新和自愈。