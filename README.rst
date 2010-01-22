==============
Django Publish
==============

Handy mixin/abstract class for providing a "publisher workflow" to arbitrary Django models.

Overview
========

* You make your model extend ``publish.models.Publishable``
* Each model instance then has some extra state information and a reference to it's "public" version, as well as extra methods to control "publishing" drafts
* You register your model with the admin and a ``ModelAdmin`` class that extends ``publish.admin.PublishableAdmin``
* The admin then only shows you "draft" (and "deleted") instances
* You work on the draft instances, then when you are happy "publish" the draft values to the public instances

How to
======

Let's say you have an app with a simple ``models.py`` that looks this this:

::

    from django.db import models
    
    class MyModel(models.Model):
        title = models.CharField(max_length=100)
        
        class Meta:
            ordering = ["title"]
        

and an ``admin.py``:

::

    from django.contrib import admin
    
    from models import MyModel
    
    class MyModelAdmin(admin.ModelAdmin):
        pass
    
    admin.site.register(MyModel, MyModelAdmin)

Then to make this model support publishing you would change the ``models.py`` thus:

::

    from django.db import models
    from publish.models import Publishable
    
    class MyModel(Publishable): # extends from Publishable instead of models.Model
        title = models.CharField(max_length=100)
        
        class Meta(Publishable.Meta): # note you should extend from Publishable.Meta
            ordering = ["title"]

That will add some extra fields to your model (so you may need to update your db).  At this point though the admin will show both the draft and published objects.  We obviously do not want that, as we want the user to edit the draft objects and then "publish" them once they are happy.  So we have to alter the ``admin.py`` file too:

::

    from django.contrib import admin
    from publish.admin import PublishableAdmin
    
    from models import MyModel
    
    class MyModelAdmin(PublishableAdmin): # just extend from PublishableAdmin instead
        pass
    
    admin.site.register(MyModel, MyModelAdmin)


At this point the admin will start showing an action to "Publish selected MyModels" as well as details of an objects "Publication status".  Publishing will show a confirmation page - much like when deleting - confirming what is about to be published (possibly including related objects).

You will then need to modify your views to handle showing only the published or draft objects.  You'll probably want some way to view both versions on your site somehow.  The ``Publishable`` model has a custom manager with some extra methods for this purpose, but you can also use a ``Q`` object on the Publishable class too:

::

    # these two will return only the "draft" objects
    MyModel.objects.draft()
    MyModel.objects.filter(Publishable.Q_DRAFT)
    
    # these will give you the "published" objects
    MyModel.objects.published()
    MyModel.objects.filter(Publishable.Q_PUBLISHED)


The latter form is handy, as the ``Q`` object can be passed in as a paramter to a view function - allowing for easy re-use of the same view function for both previewing draft objects and viewing live objects.

In addition to modifying your views, you may want to consider changing any ``get_absolute_url`` functions to correctly return the relevant URL for viewing the object - taking into account whether it is a published or draft object (using the ``is_public`` field).  The ``PublishableAdmin`` class automatically provides a link to the published (View on site) and draft (Preview on site) versions if a model has implemented ``get_absolute_url``.


Notes
=====

* ManyToManyField's specified using a "through" model will be treated as a regular reverse relationship, but will automatically be published (no need to specify it via ``PublishableMeta.publish_reverse_fields``)

Tests
=====

To run the tests for this app use the script:

::

    tests/run_tests.sh



