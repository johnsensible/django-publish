==============
Django Publish
==============

Handy mixin/abstract class for providing a "publisher workflow" to arbitrary Django models.

How it works
============

* You make your model extend ``publish.models.Publishable``
* Each model instance then has some extra state information and a reference to it's "public" version, as well as extra methods to control "publishing" drafts
* You register your model with the admin and a ``ModelAdmin`` class that extends ``publish.admin.PublishableAdmin``
* The admin then only shows you "draft" (and "deleted") instances
* You work on the draft instances, then when you are happy "publish" the draft values to the public instances

Tests
=====

To run the tests for this app use the script:

::

    tests/run_tests.sh



