from bcc import BPF
from bcc.utils import printb

prog = """
#include <linux/workqueue.h>

BPF_HASH(timeCount, struct work_struct*, u64);

int trace_queue_work_on(struct pt_regs *ctx,int cpu, struct workqueue_struct *wq, struct work_struct *work)
{
    u32 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    timeCount.update(&work,&ts);
    return 0;
}

int trace_process_one_work(struct pt_regs *ctx,struct worker *worker, struct work_struct *work)
{
    u32 pid = bpf_get_current_pid_tgid();
    u64 *tsp, delta;
    tsp = timeCount.lookup(&work);
    if (tsp == NULL) return 0;
    delta = bpf_ktime_get_ns() - *tsp;
    delta = delta / 1000;
    bpf_trace_printk("wait_for_schedule_spend:%dms", delta);
    timeCount.delete(&work);
    return 0;
}
"""

b = BPF(text=prog)

#queue_work_on将一个work加入到workqueue中
b.attach_kprobe(event="queue_work_on", fn_name="trace_queue_work_on")

#process_one_work从workqueue上取下一个work来执行
b.attach_kprobe(event="process_one_work", fn_name="trace_process_one_work")

print("tracing begin!")

while True:
    try:
        (task, pid, cpu, flags, ts, msg) = b.trace_fields()
        print("ts: %-18.9f p: %-16s pid: %-6d %s" % (ts, task, pid, msg))
        print("--------------------------------")
    except KeyboardInterrupt:
        exit()

