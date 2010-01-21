from django.contrib import admin
from django.shortcuts import get_object_or_404, render_to_response
from django.core.exceptions import PermissionDenied
from django.contrib.admin.util import unquote
from django import template
from django.utils.encoding import force_unicode

from models import Publishable
from actions import publish_selected, delete_selected

class PublishableAdmin(admin.ModelAdmin):
    
    actions = [publish_selected, delete_selected]
    change_form_template = 'admin/publish_change_form.html'
    publish_confirmation_template = None
    deleted_form_template = None
    
 
    list_display = ['__unicode__', 'publish_state']
    list_filter = ['publish_state']

    def queryset(self, request):
        # we want to show draft and deleted
        # objects in changelist in admin
        # so we can let the user select and publish them
        qs = super(PublishableAdmin, self).queryset(request)
        return qs.draft_and_deleted()

    def get_actions(self, request):
        actions = super(PublishableAdmin, self).get_actions(request)
        # replace site-wide delete selected with out own version
        if 'delete_selected' in actions:
            actions['delete_selected'] = (delete_selected, 'delete_selected', delete_selected.short_description)
        return actions

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
   
    def has_publish_permission(self, request, obj=None):
        opts = self.opts
        return request.user.has_perm(opts.app_label + '.' + self.model.PUBLISH_PERMISSION)
 
    def change_view(self, request, object_id, extra_context=None):
        # override change_view to trap permission errors
        # and determine if the object being viewed is one
        # that is marked for deletion - if so then we want
        # to show some sort of page to indicate this fact 
        try:
            return super(PublishableAdmin, self).change_view(request, object_id, extra_context)
        except PermissionDenied:
            return self.deleted_view(request, object_id, extra_context)
    
    def deleted_view(self, request, object_id, extra_context=None):
        obj = get_object_or_404(self.queryset(request), pk=unquote(object_id))
        
        # can only looked at deleted public instances
        if not obj.is_public:
            raise PermissionDenied

        opts = self.model._meta
        app_label = opts.app_label

        has_absolute_url = getattr(obj, 'get_absolute_url', None)

        context = {
            'title': 'This %s will be deleted' % force_unicode(opts.verbose_name),
            'original': obj,
            'opts': opts,
            'app_label': app_label,
            'has_absolute_url': has_absolute_url,
        }
        context.update(extra_context or {})
        context_instance = template.RequestContext(request, current_app=self.admin_site.name)
        return render_to_response(self.deleted_form_template or [
            'admin/%s/%s/deleted_form.html' % (app_label, opts.object_name.lower()),
            'admin/%s/deleted_form.html' % app_label,
            'admin/deleted_form.html'
        ], context, context_instance=context_instance)

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

