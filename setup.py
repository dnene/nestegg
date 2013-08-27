from setuptools import setup

setup(
    name='nestegg',
    version='0.0.1alpha2',
    author='Dhananjay Nene',
    author_email='dhananjay.nene@gmail.com',
    packages=['nestegg',],
    license='The MIT License (MIT)',
    description="Lightweight pypi mirror and continuous integration server",
    long_description=open("README.rst").read(),
    install_requires = [
        'bottle >= 0.11',
        'PyYAML == 3.10',
        'sh >= 1.08',
        'requests >= 1.2.3',
        'APScheduler >= 2.1.0',
    ],
    keywords="pypi mirror build release packages continuous integration testing",
    package_data = {
        'nestegg': ['views/*.tpl']
    },
    entry_points = {
        'console_scripts' : {
            'nestegg = nestegg.main:main',
        }
    },
    url='http://github.com/dnene/nestegg',
)
