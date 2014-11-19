DEBUG = True
TEMPLATE_DEBUG = DEBUG
DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = ':memory:'

SECRET_KEY = '1234567890'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': ':memory:',                      # Or path to database file if using sqlite3.
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
    }
}

STATIC_URL = '/static/'

import django

if django.VERSION < (1,4):
    INSTALLED_APPS = ( 
        'django.contrib.contenttypes',
        'django.contrib.admin',
        'django.contrib.auth',
        'publish',
    )

    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.load_template_source',
        'django.template.loaders.app_directories.load_template_source',
    )
else:
    INSTALLED_APPS = ( 
        'django.contrib.contenttypes',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.staticfiles',
        'publish',
    )

    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )
    MIDDLEWARE_CLASSES = [
        'django.contrib.messages.middleware.MessageMiddleware',
    ]


 
TESTING_PUBLISH=True
 
# enable this for coverage (using django test coverage
# http://pypi.python.org/pypi/django-test-coverage )
#TEST_RUNNER = 'django-test-coverage.runner.run_tests'
#COVERAGE_MODULES = ('publish.models', 'publish.admin', 'publish.actions', 'publish.utils', 'publish.signals')
