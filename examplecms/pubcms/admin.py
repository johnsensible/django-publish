from django.contrib import admin

from publish.admin import PublishableAdmin
from pubcms.models import Page, PageBlock, Category

class PageBlockInlineAdmin(admin.StackedInline):
    model = PageBlock
    extra = 1

class PageAdmin(PublishableAdmin):
    inlines = [PageBlockInlineAdmin]
    prepopulated_fields = {"slug": ("title",)}
    list_filter = ['publish_state', 'categories']

class CategoryAdmin(PublishableAdmin):
    prepopulated_fields = {"slug": ("name",)}

admin.site.register(Page, PageAdmin)
admin.site.register(Category, CategoryAdmin)

