from bcc import BPF
from bcc.utils import printb
from time import time

prog = """
#include <uapi/linux/ptrace.h>
#include <linux/spinlock_types_raw.h>

BPF_HASH(timeCount,u32);

int do_entry(struct pt_regs *ctx,raw_spinlock_t *lock)
{
	u32 pid;
	u64 ts, *val;

	pid = bpf_get_current_pid_tgid();
	ts = bpf_ktime_get_ns();
	timeCount.update(&pid, &ts);
	return 0;
}

int do_return(struct pt_regs *ctx,raw_spinlock_t *lock)
{
	u32 pid;
	u64 *tsp, delta;

	pid = bpf_get_current_pid_tgid();
	tsp = timeCount.lookup(&pid);

	if (tsp != 0) {
		delta = bpf_ktime_get_ns() - *tsp;
		bpf_trace_printk("called _raw_spin_lock, time_consumed: %dns", delta);
		timeCount.delete(&pid);
	}

	return 0;
}
"""

b = BPF(text=prog)
b.attach_kprobe(event="_raw_spin_lock", fn_name="do_entry")
b.attach_kretprobe(event="_raw_spin_lock", fn_name="do_return")

while True:
    try:
        (task, pid, cpu, flags, ts, msg) = b.trace_fields()
    except KeyboardInterrupt:
        exit()
    print("ts: %-18.9f p: %-16s pid: %-6d %s" % (ts, task, pid, msg))

