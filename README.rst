==============
Django Publish
==============

Handy mixin/abstract class for providing a "publisher workflow" to arbitrary Django_ models.

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
        
        class Meta(Publish.Meta): # note you should extend from Publish.Meta
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

The classes ``PublishableStackedInline`` and ``PublishableTabularInline`` are also available for handling inline editing of ``Publishable`` child models.

::

    from django.contrib import admin
    from publish.admin import PublishableAdmin, PublishableTabularInline
    
    from models import MyModel, MyChildModel
    
    class MyChildModelInline(PublishableTabularInline):
        model = MyChildModel

    class MyModelAdmin(PublishableAdmin):
        inlines = [ MyChildModelInline ]
    
    admin.site.register(MyModel, MyModelAdmin)

You'll also need to add a ``PublishMeta`` field to the parent model, so that it will also publish the child models whenever it is published:

::

    from django.db import models
    from publish.models import Publishable
    
    class MyModel(Publishable): # extends from Publishable instead of models.Model
        title = models.CharField(max_length=100)
        
        class Meta(Publish.Meta): # note you should extend from Publish.Meta
            ordering = ["title"]

        class PublishMeta(Publishable.PublishMeta):
            publish_reverse_fields = ['mychildmodel_set'] # name of reverse relation
    

    class MyChild(Publishable):
        mymodel = models.ForeignKey(MyModel)


Signals
=======

There are two signals that can be listened to during the publish process:

* ``publish.signals.pre_publish``
* ``publish.signals.post_publish``

The handlers for these signals should have the form

::

    def post_publish_handler(sender, instance, deleted, **kw):

Where ``instance`` will be the object being published - much as with the built-in Django signals pre_save_ and post_save_.  Note though that publishing an object may trigger multiple pre and post publish signals, depending on what other objects also need publishing.  However that you should not receive the same signal for the same object - only for different objects.

The signals are triggered both for publishing changes and publishing deletions.  When a change is published you will receive the draft object as the instance and ``deleted`` will be ``False``.  When a deletion is published you will receive the public instance (as that is what is being deleted) and ``deleted`` will be set to ``True``.

As with the post_delete_ signal in Django you will need to take care when using the instance if ``deleted`` is ``True``, as the object will no longer exist in the database.

Finer control
=============

You can further control the publication process by providing a ``PublishMeta`` class on your model

::

    from publish.models import Publishable
    from django.db import models

    class Page(Publishable):
        title = models.CharField(max_length=100)
        slug  = models.SlugField(max_length=100)
        body  = models.TextField()
        notes = models.TextField(blank=True)

        class PublishMeta(Publishable.PublishMeta):
            publish_exclude_fields = ['notes']

In the above class the "notes" field will be excluded from publication - it will not be copied to the public copy.

There are two other fields that can be specified:

* ``publish_reverse_fields`` - list of reverse/child relationships to publish
* ``publish_functions`` - dictionary of 'fieldname' : publish_function (same format as setattr)

Publish functions are useful if you need to run some additional action when publishing an object.  For example you may want copy a file to a public location or subtly modify a value as it gets copied.  A publish function is expected to work the same as the built-in ``setattr``, but may (and probably will) have other side-effects.

Notes
=====

* A ManyToManyField_ specified using a "through" model will be treated as a regular reverse relationship, but will automatically be published (no need to specify it via ``PublishableMeta.publish_reverse_fields``)

Tests
=====

To run the tests for this app use the script:

::

    tests/run_tests.sh


.. _Django: http://www.djangoproject.com/
.. _pre_save: http://docs.djangoproject.com/en/dev/ref/signals/#pre-save
.. _post_save: http://docs.djangoproject.com/en/dev/ref/signals/#post-save
.. _post_delete: http://docs.djangoproject.com/en/dev/ref/signals/#django.db.models.signals.post_delete
.. _ManyToManyField: http://docs.djangoproject.com/en/dev/ref/models/fields/#manytomanyfield
