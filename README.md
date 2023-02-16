# network-tracing

## 配置开发环境

[安装 BCC](https://github.com/iovisor/bcc/blob/master/INSTALL.md)，然后执行：

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
```

## 构建与打包

构建环境需要 GNU Make、CMake、Rust 工具链、GCC、LLVM、Docker、Python 3。在仓库根目录下执行下列命令打包：

```bash
# 构建 Python wheel
make distribution
# 构建容器镜像
make images
# 复制部署相关文件（compose.yml 等）
make operations
# 同时构建以上三者
make all  # 或直接 make
```

产物默认在 `dist/` 目录下。

## 部署

详见部署文件目录下的 [README](ops/deployment/README.md)。
