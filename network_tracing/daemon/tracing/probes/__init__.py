from network_tracing.daemon.tracing.probes.common import ProbeFactory
from . import demo, delay_analysis_out

probe_factories: dict[str, ProbeFactory] = {
    'demo': demo.Probe,
    'delay_analysis_out': delay_analysis_out.Probe,
}
