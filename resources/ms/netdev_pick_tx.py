from bcc import BPF
from bcc.utils import printb

prog = """
#include <linux/netdevice.h>

int do_return(struct pt_regs *ctx,struct net_device *dev, struct sk_buff *skb, struct net_device *sb_dev)
{
    //u32 pid = bpf_get_current_pid_tgid();
    int ret = PT_REGS_RC(ctx);
    bpf_trace_printk("picked_queue_index: %d",ret);
    return 0;
}
"""

b = BPF(text=prog)
b.attach_kretprobe(event="netdev_pick_tx", fn_name="do_return")

print("tracing begin!")

while True:
    try:
        (task, pid, cpu, flags, ts, msg) = b.trace_fields()
    except KeyboardInterrupt:
        exit()
    print("ts: %-18.9f p: %-16s pid: %-6d %s" % (ts, task, pid, msg))
    print("--------------------------------")

