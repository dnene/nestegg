from setuptools import setup

setup(
    name='nestegg',
    version='0.0.1alpha1',
    author='Dhananjay Nene',
    author_email='dhananjay.nene@gmail.com',
    packages=['nestegg',],
    license='The MIT License (MIT)',
    description="On-demand, lightweight, package building pypi mirror",
    install_requires = [
        'bottle >= 0.11',
        'PyYAML == 3.10',
        'sh >= 1.08',
    ],
    keywords="pypi mirror build release packages",
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
