from setuptools import setup

setup(
    name='babbisch',
    version='0.1',
    packages=['babbisch'],
    
    install_requires=['pycparser'],

    entry_points={
            'console_scripts': [
                'babbisch = babbisch:main',
            ]
    }
)
