from django import template
from django.core.exceptions import PermissionDenied
from django.contrib.admin import helpers
from django.contrib.admin.util import get_change_view_url, model_ngettext
from django.shortcuts import render_to_response
from django.utils.encoding import force_unicode
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy, ugettext as _
from django.contrib.admin.actions import delete_selected as django_delete_selected

from models import Publishable
from utils import NestedSet

def delete_selected(modeladmin, request, queryset):
    # wrap regular django delete_selected to check permissions for each object
    for obj in queryset:
        if not modeladmin.has_delete_permission(request, obj):
            raise PermissionDenied
    return django_delete_selected(modeladmin, request, queryset)
delete_selected.short_description = "Mark %(verbose_name_plural)s for deletion"

def _publish_status(model):
    state = model.get_publish_state_display()
    if not model.is_public and not model.public:
        state = '%s - not yet published' % state
    return ' (%s)' % state

def _convert_all_published_to_html(modeladmin, all_published):
    admin_site = modeladmin.admin_site
    levels_to_root=2
    
    def _to_html(published_list):
        html_list = []
        for value in published_list:
            if isinstance(value, Publishable):
                model = value.__class__
                model_name = escape(capfirst(model._meta.verbose_name))
                model_title = escape(force_unicode(value))
                model_text = '%s: %s%s' % (model_name, model_title, _publish_status(value))
                opts = model._meta                

                has_admin = model in modeladmin.admin_site._registry
                if has_admin:
                    url = get_change_view_url(opts.app_label,
                                              opts.object_name.lower(),
 	                                          value._get_pk_val(),
 	                                          admin_site,
 	                                          levels_to_root)
                    html_value = mark_safe(u'<a href="%s">%s</a>' % (url, model_text))
                else:
                    html_value = mark_safe(model_text)
            else:
                html_value = _to_html(value)
            html_list.append(html_value)
        return html_list

    return _to_html(all_published.nested_items())

def _check_permissions(modeladmin, all_published, request, perms_needed):
    admin_site = modeladmin.admin_site

    opts_seen = set()
    for instance in all_published:
        opts = instance._meta
        if opts in opts_seen:
            continue
        opts_seen.add(opts)
        
        model = instance.__class__
        other_modeladmin = admin_site._registry.get(model,None)
        if other_modeladmin:
            if not other_modeladmin.has_publish_permission(request):
                perms_needed.add(opts.verbose_name)

def publish_selected(modeladmin, request, queryset):
    opts = modeladmin.model._meta
    app_label = opts.app_label
    
    if not modeladmin.has_publish_permission(request):
        raise PermissionDenied

    all_published = NestedSet()
    for obj in queryset:
        obj.publish(dry_run=True, all_published=all_published)

    perms_needed = set()
    _check_permissions(modeladmin, all_published, request, perms_needed)
    
    if request.POST.get('post'):
        if perms_needed:
            raise PermissionDenied

        n = queryset.count()
        if n:
            all_published = NestedSet()
            queryset.publish(all_published)
            for object in all_published:
                modeladmin.log_publication(request, object)

            modeladmin.message_user(request, _("Successfully published %(count)d %(items)s.") % {
                "count": n, "items": model_ngettext(modeladmin.opts, n)
            })
            # Return None to display the change list page again.
            return None
    
    context = {
        "title": _("Publish?"),
        "object_name": force_unicode(opts.verbose_name),
        "all_published": _convert_all_published_to_html(modeladmin, all_published),
        "perms_lacking": perms_needed,
        'queryset': queryset,
        "opts": opts,
        "root_path": modeladmin.admin_site.root_path,
        "app_label": app_label,
        'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
    }

    # Display the confirmation page
    return render_to_response(modeladmin.publish_confirmation_template or [
        "admin/%s/%s/publish_selected_confirmation.html" % (app_label, opts.object_name.lower()),
        "admin/%s/publish_selected_confirmation.html" % app_label,
        "admin/publish_selected_confirmation.html"
    ], context, context_instance=template.RequestContext(request))


publish_selected.short_description = "Publish selected %(verbose_name_plural)s"
