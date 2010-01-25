from django.contrib import admin
from django.shortcuts import get_object_or_404, render_to_response
from django.core.exceptions import PermissionDenied
from django.contrib.admin.util import unquote
from django import template
from django.utils.encoding import force_unicode
from django.utils.safestring import mark_safe
from django.contrib.contenttypes.models import ContentType

from models import Publishable
from actions import publish_selected, delete_selected

def _make_form_readonly(form):
    for field in form.fields.values():
        # some widget wrap other widgets in admin
        widget = field.widget
        if hasattr(widget, 'widget'):
            widget = getattr(widget, 'widget')
        widget.attrs['disabled'] = 'disabled'
    

def _make_adminform_readonly(adminform, inline_admin_formsets):
    _make_form_readonly(adminform.form)
    for admin_formset in inline_admin_formsets:
        for form in admin_formset.formset.forms:
            _make_form_readonly(form)

def _draft_queryset(db_field, kwargs):
    # see if we need to filter the field's queryset
    model = db_field.rel.to
    if issubclass(model, Publishable):
        kwargs['queryset'] = model._default_manager.draft()

def attach_filtered_formfields(admin_class):
    # class decorator to add in extra methods that 
    # are common to several classes
    super_formfield_for_foreignkey = admin_class.formfield_for_foreignkey
    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        _draft_queryset(db_field, kwargs)
        return super_formfield_for_foreignkey(self, db_field, request, **kwargs)
    admin_class.formfield_for_foreignkey = formfield_for_foreignkey
    
    super_formfield_for_manytomany = admin_class.formfield_for_manytomany
    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        _draft_queryset(db_field, kwargs)
        return super_formfield_for_manytomany(self, db_field, request, **kwargs)
    admin_class.formfield_for_manytomany = formfield_for_manytomany
    return admin_class

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
        # replace site-wide delete selected with our own version
        if 'delete_selected' in actions:
            actions['delete_selected'] = (delete_selected, 'delete_selected', delete_selected.short_description)
        return actions

    def has_change_permission(self, request, obj=None):
        # user can never change public models directly
        # but can view old read-only copy of it if we are about to delete it
        if obj and obj.is_public:
            if request.method == 'POST' or obj.publish_state != Publishable.PUBLISH_DELETE:
                return False
        return super(PublishableAdmin, self).has_change_permission(request, obj)
    
    def has_delete_permission(self, request, obj=None):
        # use can never delete models directly
        if obj and obj.is_public:
            return False
        return super(PublishableAdmin, self).has_delete_permission(request, obj)
   
    def has_publish_permission(self, request, obj=None):
        opts = self.opts
        return request.user.has_perm(opts.app_label + '.' + opts.get_publish_permission())
    
    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj and obj.publish_state == Publishable.PUBLISH_DELETE:
            adminform, inline_admin_formsets = context['adminform'], context['inline_admin_formsets']
            _make_adminform_readonly(adminform, inline_admin_formsets)
            
            context.update({
                'title': 'This %s will be deleted' % force_unicode(self.opts.verbose_name),
            })
        
        return super(PublishableAdmin, self).render_change_form(request, context, add, change, form_url, obj)

class PublishableStackedInline(admin.StackedInline):
    pass

class PublishableTabularInline(admin.TabularInline):
    pass

# add in extra methods
for admin_class in [PublishableAdmin, PublishableStackedInline, PublishableTabularInline]:
    attach_filtered_formfields(admin_class)
