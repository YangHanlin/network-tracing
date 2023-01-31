1. _raw_spin_lock.py: 可以看到执行`_raw_spin_lock`的函数

```
ts: 932.664211000      p: b'kworker/u8:10' pid: 670    b'called _raw_spin_lock, time_consumed: 2591ns
```

3. queue_work_on: 通过追踪`queue_work_on`和`process_one_work`计算两个函数执行的时间差，来判断一个进程在runnable到running的等待时间
```
ts: 969.923199000      p: b'kworker/u8:5'  pid: 216    b'wait_for_schedule_spend:4ms'
```

3. lock_sock: 统计`__lock_sock`消耗的时间和获取锁的进程

```
ts: 1112.259333000     p: b'clash-linux'   pid: 2024   b'@entry:   lock_owned:1'
--------------------------------
ts: 1112.259354000     p: b'clash-linux'   pid: 2024   b'#return:  time_consumed:22ms'
```

4. schedule: 统计调用`schedule`函数的进程

```
ts: 1293.869757000     p: b'kworker/u8:0'  pid: 8      b'@entry:   current_time:1042788430'
```

5. cfs_rq: 获取当前cpu的等待队列(还未完成...)