from django.shortcuts import render_to_response, get_object_or_404

from models import Page

def page_detail(request, page_url, queryset):
    parts = page_url.split('/')
    parts.reverse()
    filter_params = {}
    field = 'slug'
    for slug in parts:
        filter_params[field] = slug
        field = 'parent__%s' % field
    page = get_object_or_404(queryset,**filter_params)
    
    return render_to_response("pubcms/page_detail.html", { 'page': page })
