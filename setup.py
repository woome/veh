from setuptools import setup

from veh import __version__

classifiers = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: GNU General Public License (GPL)',
    'Operating System :: OS Independent',
    'Programming Language :: Python',
    'Topic :: Utilities',
]

setup(
    name = "veh",
    version = __version__,
    description = "virtualenv for hg",
    long_description = """Tie virtualenvs to individual mercurial repositorys.""",
    license = "GNU GPL v3",
    author = "Nic Ferrier",
    author_email = "nic@ferrier.me.uk",
    url = "http://github.com/nicferrier/veh",
    download_url="http://github.com/nicferrier/veh/downloads",
    platforms = ["any"],
    packages=['veh'],
    requires=['pip', 'virtualenv', 'Mercurial'],
    entry_points = {
       'console_scripts': [
            'veh = veh:main'
        ],
    },
    classifiers =  classifiers,
    )
