---
title: "07 Common模板"
date: 1766125929
updated: 1766125929
tags: []
categories:
  - "kubenets"
---

{% raw %}
## 使用


为了能使用公共代码，我们需要添加一个 `common`依赖。在 `demo/Chart.yaml`文件最后啊添加以下内容：

```yaml
dependencies:
- name:common
version:"^0.0.5"
repository:"https://charts.helm.sh/incubator/"
```


使用辅助chart中的公共代码。首先编辑负载文件 `demo/templates/deployment.yaml`如下：

```yaml
&#123;&#123;- template "common.deployment" (list . "demo.deployment") -&#125;&#125;
&#123;&#123;- define "demo.deployment" -&#125;&#125;
## Define overrides for your Deployment resource here, e.g.
apiVersion: apps/v1
spec:
  replicas: &#123;&#123; .Values.replicaCount &#125;&#125;
  selector:
    matchLabels:
      &#123;&#123;- include "demo.selectorLabels" . | nindent 6 &#125;&#125;
  template:
    metadata:
      labels:
        &#123;&#123;- include "demo.selectorLabels" . | nindent 8 &#125;&#125;

&#123;&#123;- end -&#125;&#125;
```





`demo/templates/service.yaml`变成了下面这样：

```yaml
&#123;&#123;- template "common.service" (list . "demo.service") -&#125;&#125;
&#123;&#123;- define "demo.service" -&#125;&#125;
## Define overrides for your Service resource here, e.g.
# metadata:
#   labels:
#     custom: label
# spec:
#   ports:
#   - port: 8080
&#123;&#123;- end -&#125;&#125;
```




* 模板文件的名称应该反映名称中的资源类型。比如：`foo-pod.yaml`， `bar-svc.yaml`
* yaml注释中的模板字符串仍然会被解析
* 镜像使用固定版本或者范围版本。
* define是全局的模板，需要给不同的模板添加命名空间
{% endraw %}
