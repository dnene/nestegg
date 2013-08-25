from setuptools import setup

setup(
    name='nestegg',
    version='0.1dev',
    packages=['nestegg',],
    license='The MIT License (MIT)',
    long_description="On-demand, lightweight, package building pypi mirror",
    install_requires = [
        'bottle >= 0.11',
        'PyYAML == 3.10',
        'sh >= 1.08',
    ],
)
