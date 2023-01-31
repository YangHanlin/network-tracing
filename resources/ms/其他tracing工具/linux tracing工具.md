linux tracing工具

# linux tracing工具

linux提供的trace工具: strace(跟踪系统调用), ftrace(跟踪内核函数调用栈), perf(分析系统的性能)



## strace

syscall trace，用来跟踪进程中系统调用的执行耗时，详细参数，和系统调用相关的统计信息

使用

```
strace -r [--attach pid]/[-p pid]/command
```

![image-20220927121813783](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20220927121813783.png)

可以看到该进程/命令依次执行的系统调用的耗时和详细的参数

使用

```
strace -c -w
```

![image-20220927122130665](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20220927122130665.png)

-c 表示查看占比统计信息，-w可以看到每个系统调用的总耗时。



## ftrace

function trace系统使用文件系统作为操作工具，使用echo将配置值写入到对应的文件中来实现配置，使用cat将tracing结果打印出来。

直接使用ftrace提供的文件操作方式比较繁琐，可以使用`trace-cmd`(cmd)和`kernelshark`(gui)作为ftrace的前端工具。

使用前需要挂载debugfs，一般发行版会自动挂载，如需手动挂载使用如下命令

```bash
mount -t debugfs debugfs /sys/kernel/debug
```

使用

```bash
 sudo cat /sys/kernel/debug/available_tracers
```

来打印所有可用的trace方式，使用默认内核的tracer有限，若想使用其他tracer需要在编译配置中开启

```
hwlat blk mmiotrace function_graph wakeup_dl wakeup_rt wakeup function nop
```

常用的tracer的介绍如下

> “function”
>
> Function call tracer to trace all kernel functions.
>
> “function_graph”
>
> Similar to the function tracer except that the function tracer probes the functions on their entry whereas the function graph tracer traces on both entry and exit of the functions. It then provides the ability to draw a graph of function calls similar to C code source.
>

*常用ftrace的`function_graph`来打印系统函数的调用栈和耗时*



### 对进程的内核函数调用栈分析

使用如下命令跟踪chrome进程发生`net:netif_receive_skb`事件时的系统调用图和耗时

```bash
sudo trace-cmd record -p function_graph -e net:netif_receive_skb -P 2062
```

命令解释：

1. `trace-cmd record`子命令用来开始一次tracing，结果如果不用-o指定输出文件，会默认在当前路径下生成`trace.dat`文件来保存结果
2. `-p function_graph`表明此次tracing使用的tracer，查看函数调用流程和耗时
3. `-e net:netif_receive_skb`表明跟踪的事件，当前事件触发时才会记录tracing结果
4. `-P 2062`为跟踪的进程pid

可供跟踪的事件可用

```bash
sudo perf list | grep skb
```

![image-20220925224011331](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20220925224011331.png)

生成的结果`trace.dat`需使用`trace-cmd report`来查看，可将其结果输出到文本文件中

```bash
sudo trace-cmd report > traceRes.txt
```

![trace-cmd-Result](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/trace-cmd-Result.png)

配合vscode的搜索功能，可看到每个函数的调用关系和函数级的具体耗时

`trace.dat`文件也可以使用`kernelshark`来查看，可以进行函数，进程，cpu等级别的过滤，但函数调用关系因为缩进不对看的不是很清楚，效果如图![raw_spin_lock](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/raw_spin_lock.png)



## perf

perf基于ftrace，两者命令有许多相似之处，但perf更偏向对跟踪数据的总体统计，便以从宏观的角度去发现进程，系统中的性能优化点。

### perf top

```bash
perf top [-p pid] [-e event]
```

不加pid默认跟踪整个系统范围内的函数调用耗时占比，event和ftrace中的，[k]表示内核函数，[.]表示用户态函数

![image-20220927131548430](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20220927131548430.png)



### perf stat

```bash
perf stat [-p pid]
```

![image-20220927133020305](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20220927133020305.png)

可以查看一个进程的cpu的cycle使用数，上下文切换数，cpu迁移数，和ipc,branch-misses等数据

### perf record

和trace-cmd的record相似，会生成`perf.data`文件，使用`perf report`打开。`perf record`表示采集系统事件, 没有使用 -e 指定采集事件, 则默认采集 cycles(即 CPU clock 周期)，用它记录一段时间内的对应事件触发时函数的用时占比。-g表示记录函数调用栈

```bash
sudo perf record -e sched:sched_switch -g
sudo perf report
```

![image-20220927135449134](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20220927135449134.png)

### perf生成火焰图

首先下载生成火焰图工具的代码仓库

```bash
git clone https://github.com/brendangregg/FlameGraph.git
```

| 流程       | 描述                                                         | 脚本                          |
| ---------- | ------------------------------------------------------------ | ----------------------------- |
| 捕获堆栈   | 使用 perf/systemtap/dtrace 等工具抓取程序的运行堆栈          | perf/systemtap/dtrace等       |
| 折叠堆栈   | trace 工具抓取的系统和程序运行每一时刻的堆栈信息, 需要对他们进行分析组合, 将重复的堆栈累计在一起, 从而体现出负载和关键路径 | FlameGraph的stackcollapse工具 |
| 生成火焰图 | 分析 stackcollapse 输出的堆栈信息生成火焰图                  | flamegraph.pl                 |

根据流程，依次执行以下命令

```
sudo perf record -F 100 -p 27252 -g -- sleep 5
```

 -F 100 表示每秒采集100 次, -p 27252是进程号, sleep 5 则是持续 5 秒

```bash
# 解析perf收集的信息
perf script -i perf.data &> perf.unfold
# 生成折叠后的调用栈(.pl脚本位于FlameGraph工具仓库)
./stackcollapse-perf.pl perf.unfold &> perf.folded
# 生成火焰图
./flamegraph.pl perf.folded > perf.svg

```

​	把上述命令利用管道符链接起来如下

```bash
perf script | ./stackcollapse-perf.pl | ./flamegraph.pl > perf.svg
```


生成的perf.svg使用浏览器打开即可

![image-20220927141552508](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20220927141552508.png)

x轴宽度表示该函数的调用次数，而y轴表示函数调用栈的深度，耗时和调用次数与颜色无关，优化时应当关注x轴较宽的函数



## bpftrace

可以使用`bpftrace -l '*name*'` 来搜索当前机器上支持的，包含`name`的ebpf程序挂载点

![image-20221008174946345](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/image-20221008174946345.png)

## tracing工具对比

![trace工具对比](https://lunqituchuang.oss-cn-hangzhou.aliyuncs.com/trace工具对比.png)

[tracing工具思维导图(密码: linux)](https://www.processon.com/view/link/62ef5b4e0791292e9d378261#map)