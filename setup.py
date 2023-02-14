from setuptools import find_packages, setup

setup(
    name='network-tracing',
    version='0.1.0',
    packages=find_packages(include=[
        'network_tracing',
        'network_tracing.*',
    ]),
    entry_points={
        'console_scripts': [
            'ntd=network_tracing.daemon.main:main',
            'ntctl=network_tracing.cli.main:main',
        ],
    },
    install_requires=[
        # Daemon dependencies
        'bcc',  # this should be manually installed
        'flask',
        'flask-cors',

        # CLI dependencies
        'requests',
        'influxdb-client[ciso]',
    ],
    python_requires='>= 3.10',
    include_package_data=True,
)
