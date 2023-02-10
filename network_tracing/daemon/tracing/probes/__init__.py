from network_tracing.daemon.tracing.probes.models import ProbeFactory
from . import demo, delay_analysis_in, delay_analysis_in_v6, delay_analysis_out, delay_analysis_out_v6

probe_factories: dict[str, ProbeFactory] = {
    'demo': demo.Probe,
    'delay_analysis_in': delay_analysis_in.Probe,
    'delay_analysis_in_v6': delay_analysis_in_v6.Probe,
    'delay_analysis_out': delay_analysis_out.Probe,
    'delay_analysis_out_v6': delay_analysis_out_v6.Probe,
}
