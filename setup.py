import os
from setuptools import setup

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))
with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()
setup(
    name='video-evms',
    version='0.1',
    package_data={'video_evms': ['static/*']},
    packages=['video_evms'],
    description='Video player extension for Open edX',
    long_description=README,
)
