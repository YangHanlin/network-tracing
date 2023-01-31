from bcc import BPF
from bcc.utils import printb

prog = """
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
"""

b = BPF(text=prog)
b.attach_kprobe(event="schedule", fn_name="do_entry")
b.attach_kretprobe(event="schedule", fn_name="do_return")

print("tracing begin!")

while True:
    try:
        (task, pid, cpu, flags, ts, msg) = b.trace_fields()
        print("ts: %-18.9f p: %-16s pid: %-6d %s" % (ts, task, pid, msg))
        print("--------------------------------")
    except KeyboardInterrupt:
        exit()

