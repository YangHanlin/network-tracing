from network_tracing.daemon.tracing.probes.common import ProbeFactory
from . import demo

probe_factories: dict[str, ProbeFactory] = {
    'demo': demo.Probe,
}
