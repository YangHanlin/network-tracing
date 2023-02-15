from setuptools import find_packages, setup

NAME = 'network-tracing'
PACKAGE_PATTERNS = [
    'network_tracing',
    'network_tracing.*',
]
ENTRY_POINTS = {
    'console_scripts': [
        'ntd=network_tracing.daemon.main:main',
        'ntctl=network_tracing.cli.main:main',
    ],
}
INSTALL_REQUIRES = [
    # Daemon dependencies
    'bcc',  # this should be manually installed
    'flask',
    'flask-cors',

    # CLI dependencies
    'requests',
    'influxdb-client[ciso]',
]
SETUP_REQUIRES = [
    'setuptools-git-versioning<2',
]
PYTHON_REQUIRES = '>=3.10'

EXTRA_OPTIONS = {
    'setuptools_git_versioning': {
        'enabled': True,
    },
}

if __name__ == '__main__':
    setup(
        name=NAME,
        packages=find_packages(include=PACKAGE_PATTERNS),
        entry_points=ENTRY_POINTS,
        install_requires=INSTALL_REQUIRES,
        setup_requires=SETUP_REQUIRES,
        python_requires=PYTHON_REQUIRES,
        include_package_data=True,
        **EXTRA_OPTIONS
    )
