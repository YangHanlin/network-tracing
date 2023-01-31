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
    bpf_trace_printk("#return:  time_consumed:%d", delta);
    timeCount.delete(&pid);
    return 0;
}