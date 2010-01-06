#!/bin/sh
# run from parent directory
django-admin.py syncdb --pythonpath=. --pythonpath=examplecms --settings=settings
