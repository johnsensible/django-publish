from django.contrib import admin

from publish.admin import PublishableAdmin
from pubcms.models import Page

class PageAdmin(PublishableAdmin):
    prepopulated_fields = {"slug": ("title",)}

admin.site.register(Page, PageAdmin)
