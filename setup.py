from setuptools import setup, find_packages
 
setup(
    name='django-publish',
    version=__import__('publish').__version__,
    description='Handy mixin/abstract class for providing a "publisher workflow" to arbitrary Django models.',
    long_description=open('README.rst').read(),
    author='John Montgomery',
    author_email='john@sensibledevelopment.com',
    url='http://github.com/johnsensible/django-publish',
    download_url='http://github.com/johnsensible/django-publish/downloads',
    license='BSD',
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    zip_safe=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
