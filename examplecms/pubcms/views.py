from models import Page

def page_detail(request, page_url, queryset):
    parts = page_url.split('/')
    

