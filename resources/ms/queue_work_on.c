#include <linux/workqueue.h>
BPF_HASH(timeCount,struct work_struct *work,u64);
//BPF_HASH(workSet,struct work_struct *work,u32);
int queue_work_on(struct pt_regs *ctx,int cpu, struct workqueue_struct *wq, struct work_struct *work)
{
    u32 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    //workSet.update(work,1);
    timeCount.update(work,&ts);
    return 0;
}

int process_one_work(struct pt_regs *ctx,struct worker *worker, struct work_struct *work)
{
    u32 pid = bpf_get_current_pid_tgid();
    //u64 ts = bpf_ktime_get_ns();

    u64 *tsp, delta;
    tsp = timeCount.lookup(work);
    if (tsp == NULL) return 0;
    delta = bpf_ktime_get_ns() - *tsp;

    bpf_trace_printk("#return:  time_consumed:%dms", delta);
    timeCount.delete(work);

    return 0;
}