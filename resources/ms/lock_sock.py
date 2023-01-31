from bcc import BPF
from bcc.utils import printb
import time
import psutil
import sys
# Debug output compiled LLVM IR.
DEBUG_LLVM_IR = 0x1
# Debug output loaded BPF bytecode and register state on branches.
DEBUG_BPF = 0x2
# Debug output pre-processor result.
DEBUG_PREPROCESSOR = 0x4
# Debug output ASM instructions embedded with source.
DEBUG_SOURCE = 0x8
# Debug output register state on all instructions in addition to DEBUG_BPF.
DEBUG_BPF_REGISTER_STATE = 0x10
# Debug BTF.
DEBUG_BTF = 0x20
prog = """
#include <net/sock.h>

BPF_HASH(timeCount,u32);

int do_entry(struct pt_regs *ctx,struct sock *sk)
{
    u32 pid = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();
    int lock_owned = sk->sk_lock.owned;
    bpf_trace_printk("@entry:   lock_owned:%d", lock_owned);
    timeCount.update(&pid,&ts);
    return 0;
}

int do_return(struct pt_regs *ctx,struct sock *sk)
{
    u32 pid = bpf_get_current_pid_tgid();
    int lock_owned = sk->sk_lock.owned;
    u64 *tsp, delta;
    tsp = timeCount.lookup(&pid);
    if (tsp == NULL) return 0;
    delta = bpf_ktime_get_ns() - *tsp;
    delta = delta /1000;
    bpf_trace_printk("#return:  time_consumed:%dms", delta);
    timeCount.delete(&pid);
    return 0;
}
"""

b = BPF(text=prog)
b.attach_kprobe(event="__lock_sock", fn_name="do_entry")
b.attach_kretprobe(event="__lock_sock", fn_name="do_return")

# format output
# def print_event(ctx, data, size):
#     out = b["out"].event(data)
#     pid = psutil.Process(out.pid)
#     print("pid:%-8d process_name:%-15s time_consumed:%-8d lock_owned:%-8d" %(out.pid,pid.name(),out.ts,out.lock_owned))
#     sys.stdout.flush()

print("tracing begin!")
# b["out"].open_perf_buffer(print_event)

while True:
    try:
        (task, pid, cpu, flags, ts, msg) = b.trace_fields()
        print("ts: %-18.9f p: %-16s pid: %-6d %s" % (ts, task, pid, msg))
        print("--------------------------------")
    except KeyboardInterrupt:
        exit()

