DEBUG = True
TEMPLATE_DEBUG = DEBUG
DATABASE_ENGINE = 'sqlite3'
DATABASE_NAME = ':memory:'
INSTALLED_APPS = ( 'publish', )
 
TESTING_PUBLISH=True
 
# enable this for coverage (using django test coverage
# http://pypi.python.org/pypi/django-test-coverage )
TEST_RUNNER = 'django-test-coverage.runner.run_tests'
COVERAGE_MODULES = ('publish.models', 'publish.admin', 'publish.views', 'publish.actions', 'publish.utils')
