from django.shortcuts import render_to_response

from models import Page

def page_detail(request, page_url, queryset):
    print page_url
    parts = page_url.split('/')
    parts.reverse()
    filter_params = {}
    field = 'slug'
    for slug in parts:
        filter_params[field] = slug
        field = 'parent__%s' % field
    print filter_params
    page = queryset.get(**filter_params)
    
    return render_to_response("pubcms/page_detail.html", { 'page': page })
