from pathlib import Path
from setuptools import setup


def get_requirements():
    with open(Path(__file__).parent / 'requirements.txt',
              'r',
              encoding='utf-8') as f:

        return list(
            filter(lambda line: line and not line.startswith('#'),
                   map(lambda line: line.strip(), f.readlines())))


setup(
    name='network-tracing',
    version='0.1.0',
    packages=['network_tracing'],
    entry_points={
        'console_scripts': [
            'ntd=network_tracing.daemon.main:main',
            'ntctl=network_tracing.cli.main:main',
        ],
    },
    install_requires=get_requirements(),
)
