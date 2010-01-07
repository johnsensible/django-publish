from django.contrib import admin

from models import Publishable
from actions import publish_selected

class PublishableAdmin(admin.ModelAdmin):
    
    actions = [publish_selected]
    publish_confirmation_template = None
    
    list_display = ['__unicode__', 'publish_state']

    def queryset(self, request):
        # we want to show draft and deleted
        # objects in changelist in admin
        # so we can let the user select and publish them
        qs = super(PublishableAdmin, self).queryset(request)
        return qs.draft_and_deleted()

    def has_change_permission(self, request, obj=None):
        # use can never change public models directly
        if obj and obj.is_public:
            return False
        return super(PublishableAdmin, self).has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        # use can never delete models directly
        if obj and obj.is_public:
            return False
        return super(PublishableAdmin, self).has_delete_permission(request, obj)

    def _draft_queryset(self, db_field, kwargs):
        # see if we need to filter the field's queryset
        model = db_field.rel.to
        if issubclass(model, Publishable):
            kwargs['queryset'] = model._default_manager.draft()

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        self._draft_queryset(db_field, kwargs)
        return super(PublishableAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
    
    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        self._draft_queryset(db_field, kwargs)
        return super(PublishableAdmin, self).formfield_for_manytomany(db_field, request, **kwargs)

