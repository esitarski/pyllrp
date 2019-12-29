from distutils.core import setup
setup(
    name='pyllrp',
    version='3.0.0',
    author='Edward Sitarski',
    author_email='edward.sitarski@gmail.com',
    url='http://www.sites.google.com/site/crossmgrsoftware/',
    packages=['pyllrp'],
    license='License.txt',
    include_package_data=True,
    description='pyllrp: a pure Python implementation of LLRP (Low Level Reader Protocol).',
    install_requires=['bitstring >= 3.1.1', 'six'],
    classifiers=['Development Status :: 3 - Alpha', 'License :: OSI Approved :: MIT License', 'Programming Language :: Python :: 2.7 :: Python :: 3', 'Operating System :: OS Independent'],
    long_description=open('README.txt').read(),
)
