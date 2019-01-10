from setuptools import setup

setup(
    name='snapshotalyzer',
    version='0.1',
    author='Alex Meyer',
    author_email="alex.meyer62@gmail.com",
    description="Snapshotalyzer is a tool to manage EC2 instances in your AWS environment",
    license="GPLv3",
    packages=['shotty'],
    url="https://github.com/TravelingLex/snapshotalyzer",
    install_requires=[
        'click',
        'boto3'
    ],
    entry_points='''
        [console_scripts]
        shotty=shotty.shotty:cli
    ''',
)