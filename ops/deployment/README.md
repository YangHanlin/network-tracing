# 安装与部署

**注：** 下列命令假设当前位于构建产物中的 `network-tracing-ops` 目录下。如果是在仓库 `ops/deployment` 目录下看到此文档，需要在实际执行下列命令之前通过 `make` 生成构建产物，并在构建产物目录下操作。

## 容器化部署

从 GitHub 仓库 `main` 分支构建的应用镜像被推到了 Docker Hub，可以直接拉下使用：

```bash
docker pull hanlinyang/network-tracing:latest
docker tag hanlinyang/network-tracing:latest network-tracing:latest
```

如果不想使用 Docker Hub 上的镜像，也可以从构建产物中加载镜像：

```bash
docker load -i ../network-tracing-images.tar
```

在启动守护进程之前，需要确保其宿主机上安装了内核头文件（如通过 `sudo apt-get install -y linux-headers-$(uname -r)`）。守护进程容器中的 BCC 依赖于宿主机的内核头文件。

在需要观测的机器上，执行下列命令部署守护进程（`ntd`）：

```bash
pushd daemon
docker compose up -d  # 可以利用环境变量指定配置项
popd
```

在同一台机器或另一台机器上，启动存储、分析数据需要的 InfluxDB 与 Grafana：

```bash
pushd analysis
docker compose up -d
popd
```

利用 CLI 工具（`ntctl`），可以启动观测，并将采集到的数据导入 InfluxDB 供分析。如果上述守护进程与 InfluxDB/Grafana 部署在同一台机器上，可以直接使用示例配置：

```bash
pushd bridge-example
NTCTL_START_OPTIONS="传给 ntctl start 命令的参数" docker compose up -d
popd
```

如果部署在不同机器上，可以基于示例配置修改所对接的 API 地址等配置项；或者直接在宿主机上安装运行 CLI 工具（见下节）。

## 本地部署

在安装应用之前，需要手动[安装 BCC](https://github.com/iovisor/bcc/blob/master/INSTALL.md)。

执行下列命令安装应用（包括守护进程 `ntd` 与 CLI 工具 `ntctl`）：

```bash
sudo python3 -m pip install ../network-tracing/*.whl
```

在被观测的机器上，启动守护进程：

```bash
ntd
```

在同一台机器或另一台机器上部署配置 InfluxDB 与 Grafana。可以使用 `analysis` 目录下的配置直接容器化部署（见上节），也可以在本地手动部署。手动部署时，Grafana 需要的数据源与 Dashboard 配置可见 `analysis/grafana/` 目录。

使用 CLI 工具启动观测：

```bash
ntctl --base-url http://守护进程机器 IP:10032 start 参数
```

启动成功后输出任务 ID。然后可以使用 CLI 工具将守护进程采集的数据导入 InfluxDB：

```bash
export INFLUXDB_V2_URL=http://InfluxDB 机器 IP:8086
export INFLUXDB_V2_ORG=-
ntctl --base-url http://守护进程机器 IP:10032 events --action upload 任务 ID
```
