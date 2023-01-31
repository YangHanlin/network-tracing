#include <linux/sched.h>
BPF_HASH(timeCount,u32);

int do_entry(struct pt_regs *ctx)
{
    u32 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    bpf_trace_printk("@entry:   current_time:%d", ts);
    timeCount.update(&pid,&ts);
    return 0;
}

int do_return(struct pt_regs *ctx)
{
    u32 pid = bpf_get_current_pid_tgid();
    u64 *tsp, delta;
    tsp = timeCount.lookup(&pid);
    if (tsp == NULL) return 0;
    delta = bpf_ktime_get_ns() - *tsp;
    bpf_trace_printk("#return:  time_consumed:%dns", delta);
    timeCount.delete(&pid);
    return 0;
}