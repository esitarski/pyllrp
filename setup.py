from distutils.core import setup
setup(
    name='pyllrp',
    version='3.1.1',
    author='Edward Sitarski',
    author_email='edward.sitarski@gmail.com',
    url='http://www.sites.google.com/site/crossmgrsoftware/',
    packages=['pyllrp'],
    license='License.txt',
    include_package_data=True,
    description='pyllrp: a pure Python implementation of LLRP (Low Level Reader Protocol).',
    install_requires=['bitstring >= 3.1.1',],
    classifiers=['Development Status :: 5 - Production/Stable', 'License :: OSI Approved :: MIT License', 'Programming Language :: Python :: 3', 'Operating System :: OS Independent'],
    long_description=open('README.md').read(),
	long_description_content_type='text/markdown',   
)
