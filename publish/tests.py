from django.conf import settings
 
if getattr(settings, 'TESTING_PUBLISH', False):
    import unittest
    from django.test import TransactionTestCase
    from django.contrib.admin.sites import AdminSite
    from django.contrib.admin import StackedInline
    from django.forms.models import ModelChoiceField, ModelMultipleChoiceField
    from django.conf.urls.defaults import *
    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    from publish.models import Publishable, FlatPage, Site, Page, PageBlock, \
                               Author, Tag, PageTagOrder, Comment, update_pub_date
    from publish.admin import PublishableAdmin
    from publish.actions import publish_selected, delete_selected, \
                                _convert_all_published_to_html, _publish_status
    from publish.utils import NestedSet
    
    class TestNestedSet(unittest.TestCase):
        
        def setUp(self):
            super(TestNestedSet, self).setUp()
            self.nested = NestedSet()

        def test_len(self):
            self.failUnlessEqual(0, len(self.nested))
            self.nested.add('one')
            self.failUnlessEqual(1, len(self.nested))
            self.nested.add('two')
            self.failUnlessEqual(2, len(self.nested))
            self.nested.add('one2', parent='one')
            self.failUnlessEqual(3, len(self.nested))

        def test_contains(self):
            self.failIf('one' in self.nested)
            self.nested.add('one')
            self.failUnless('one' in self.nested)
            self.nested.add('one2', parent='one')
            self.failUnless('one2' in self.nested)

        def test_nested_items(self):
            self.failUnlessEqual([], self.nested.nested_items())
            self.nested.add('one')
            self.failUnlessEqual(['one'], self.nested.nested_items())
            self.nested.add('two')
            self.nested.add('one2', parent='one')
            self.failUnlessEqual(['one', ['one2'], 'two'], self.nested.nested_items())
            self.nested.add('one2-1', parent='one2')
            self.nested.add('one2-2', parent='one2')
            self.failUnlessEqual(['one', ['one2', ['one2-1', 'one2-2']], 'two'], self.nested.nested_items())

        def test_iter(self):
            self.failUnlessEqual(set(), set(self.nested))
            
            self.nested.add('one')
            self.failUnlessEqual(set(['one']), set(self.nested))

            self.nested.add('two', parent='one')
            self.failUnlessEqual(set(['one', 'two']), set(self.nested))

            items = set(['one', 'two'])

            for item in self.nested:
                self.failUnless(item in items)
                items.remove(item)
            
            self.failUnlessEqual(set(), items)
 
    class TestBasicPublishable(TransactionTestCase):
        
        def setUp(self):
            super(TestBasicPublishable, self).setUp()
            self.flat_page = FlatPage(url='/my-page', title='my page',
                                      content='here is some content', 
                                      enable_comments=False,
                                      registration_required=True)
        
        def test_get_public_absolute_url(self):
            self.failUnlessEqual('/my-page*', self.flat_page.get_absolute_url())
            # public absolute url doesn't exist until published
            try:
                self.flat_page.get_public_absolute_url()
                self.fail()
            except AttributeError:
                pass
            self.flat_page.save()
            self.flat_page.publish()
            self.failUnlessEqual('/my-page', self.flat_page.get_public_absolute_url())

        def test_save_marks_changed(self):
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save(mark_changed=False)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)
        
        def test_publish_excludes_fields(self):
            self.flat_page.save()
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failIfEqual(self.flat_page.id, self.flat_page.public.id)
            self.failUnless(self.flat_page.public.is_public)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.public.publish_state)

        def test_publish_changes_check_is_not_public(self):
            try:
                self.flat_page.is_public = True
                self.flat_page.publish_changes()
                self.fail("Should not be able to publish public models")
            except AssertionError:
                pass

        def test_publish_check_has_id(self):
            try:
                self.flat_page.publish()
                self.fail("Should not be able to publish unsaved models")
            except AssertionError:
                pass
        
        def test_publish_simple_fields(self):
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)
            self.failIf(self.flat_page.public) # should not be a public version yet
            
            self.flat_page.publish()
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.failUnless(self.flat_page.public)
            
            for field in 'url', 'title', 'content', 'enable_comments', 'registration_required': 
                self.failUnlessEqual(getattr(self.flat_page, field), getattr(self.flat_page.public, field))
        
        def test_published_simple_field_repeated(self):
            self.flat_page.save()
            self.flat_page.publish()
            
            public = self.flat_page.public
            self.failUnless(public)
            
            self.flat_page.title = 'New Title'
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)

            self.failUnlessEqual(public, self.flat_page.public)
            self.failIfEqual(public.title, self.flat_page.title)

            self.flat_page.publish()
            self.failUnlessEqual(public, self.flat_page.public)
            self.failUnlessEqual(public.title, self.flat_page.title)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
        
        def test_publish_records_published(self):
            all_published = NestedSet()
            self.flat_page.save()
            self.flat_page.publish(all_published=all_published)
            self.failUnlessEqual(1, len(all_published))
            self.failUnless(self.flat_page in all_published)
            self.failUnless(self.flat_page.public)

        def test_publish_dryrun(self):
            all_published = NestedSet()
            self.flat_page.save()
            self.flat_page.publish(dry_run=True, all_published=all_published)
            self.failUnlessEqual(1, len(all_published))
            self.failUnless(self.flat_page in all_published)
            self.failIf(self.flat_page.public)
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)

        def test_delete_after_publish(self):
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public
            self.failUnless(public)
            
            self.flat_page.delete()
            self.failUnlessEqual(Publishable.PUBLISH_DELETE, public.publish_state)

            self.failUnlessEqual([public], list(FlatPage.objects.all()))

        def test_delete_before_publish(self):
            self.flat_page.save()
            self.flat_page.delete()
            self.failUnlessEqual([], list(FlatPage.objects.all()))

        def test_publish_deletions(self):
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public
            
            self.flat_page.delete()
            self.failUnlessEqual([public], list(FlatPage.objects.all()))
                       
            public.publish()
            self.failUnlessEqual([], list(FlatPage.objects.all()))

        def test_publish_deletions_checks_flag(self):
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public
            
            self.failUnlessEqual(set([self.flat_page, public]), set(FlatPage.objects.all()))
                       
            public.publish()
            self.failUnlessEqual(set([self.flat_page, public]), set(FlatPage.objects.all()))
        
        def test_publish_deletions_checks_all_published(self):
            # make sure publish_deletions looks at all_published arg
            # to see if we need to actually publish the deletion
            self.flat_page.save()
            self.flat_page.publish()
            public = self.flat_page.public
            
            self.flat_page.delete()
            
            self.failUnlessEqual(set([public]), set(FlatPage.objects.all()))
            
            all_published = NestedSet()
            all_published.add(public)
            
            public.publish(all_published=all_published)
            self.failUnlessEqual(set([public]), set(FlatPage.objects.all()))

    class TestPublishableManager(TransactionTestCase):
        
        def setUp(self):
            super(TransactionTestCase, self).setUp()
            self.flat_page1 = FlatPage.objects.create(url='/url1/', title='title 1')
            self.flat_page2 = FlatPage.objects.create(url='/url2/', title='title 2')
        
        def test_all(self): 
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.all()))
            
            # publishing will produce extra copies
            self.flat_page1.publish()
            self.failUnlessEqual(3, FlatPage.objects.count())
            
            self.flat_page2.publish()
            self.failUnlessEqual(4, FlatPage.objects.count())


        def test_changed(self):
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.changed()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page2], list(FlatPage.objects.changed()))
            
            self.flat_page2.publish()
            self.failUnlessEqual([], list(FlatPage.objects.changed()))
        
        def test_draft(self):
            # draft should stay the same pretty much always
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))
            
            self.flat_page2.publish()
            self.failUnlessEqual([self.flat_page1, self.flat_page2], list(FlatPage.objects.draft()))
        
        def test_published(self):
            self.failUnlessEqual([], list(FlatPage.objects.published()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([self.flat_page1.public], list(FlatPage.objects.published()))
            
            self.flat_page2.publish()
            self.failUnlessEqual([self.flat_page1.public, self.flat_page2.public], list(FlatPage.objects.published()))

        def test_deleted(self):
            self.failUnlessEqual([], list(FlatPage.objects.deleted()))
            
            self.flat_page1.publish()
            self.failUnlessEqual([], list(FlatPage.objects.deleted()))

            public = self.flat_page1.public
            self.flat_page1.delete()
            self.failUnlessEqual([public], list(FlatPage.objects.deleted()))

        def test_draft_and_deleted(self):
            self.failUnlessEqual(set([self.flat_page1, self.flat_page2]), set(FlatPage.objects.draft_and_deleted()))
            
            self.flat_page1.publish()
            self.failUnlessEqual(set([self.flat_page1, self.flat_page2]), set(FlatPage.objects.draft_and_deleted()))
            
            public1 = self.flat_page1.public
            self.flat_page1.delete()
            self.failUnlessEqual(set([public1, self.flat_page2]), set(FlatPage.objects.draft_and_deleted()))


        def test_delete(self):
            # delete is overriden, so it marks the public instances
            self.flat_page1.publish()
            public1 = self.flat_page1.public
            
            FlatPage.objects.draft().delete()
            
            self.failUnlessEqual([public1], list(FlatPage.objects.all()))
            self.failUnlessEqual([public1], list(FlatPage.objects.deleted()))
        
        def test_publish(self):
            self.failUnlessEqual([], list(FlatPage.objects.published()))
            
            FlatPage.objects.draft().publish()

            flat_page1 = FlatPage.objects.get(id=self.flat_page1.id)
            flat_page2 = FlatPage.objects.get(id=self.flat_page2.id)
 
            self.failUnlessEqual(set([flat_page1.public, flat_page2.public]), set(FlatPage.objects.published()))
             
        

    class TestPublishableManyToMany(TransactionTestCase):
        
        def setUp(self):
            super(TestPublishableManyToMany, self).setUp()
            self.flat_page = FlatPage.objects.create(
                                      url='/my-page', title='my page',
                                      content='here is some content', 
                                      enable_comments=False,
                                      registration_required=True)
            self.site1 = Site.objects.create(title='my site', domain='mysite.com')
            self.site2 = Site.objects.create(title='a site', domain='asite.com')
        
        def test_publish_no_sites(self):
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))
        
        def test_publish_add_site(self):
            self.flat_page.sites.add(self.site1)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))
        
        def test_publish_repeated_add_site(self):
            self.flat_page.sites.add(self.site1)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))
            
            self.flat_page.sites.add(self.site2)
            self.failUnlessEqual([self.site1], list(self.flat_page.public.sites.all()))

            self.flat_page.publish()
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))
        
        def test_publish_remove_site(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.sites.remove(self.site1)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.publish()
            self.failUnlessEqual([self.site2], list(self.flat_page.public.sites.all()))

        def test_publish_clear_sites(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.failUnless(self.flat_page.public)
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.sites.clear()
            self.failUnlessEqual([self.site1, self.site2], list(self.flat_page.public.sites.order_by('id')))

            self.flat_page.publish()
            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))

        def test_publish_sites_cleared_not_deleted(self):
            self.flat_page.sites.add(self.site1, self.site2)
            self.flat_page.publish()
            self.flat_page.sites.clear()
            self.flat_page.publish()

            self.failUnlessEqual([], list(self.flat_page.public.sites.all()))
            
            self.failIfEqual([], list(Site.objects.all()))

            


    class TestPublishableRecursiveForeignKey(TransactionTestCase):

        def setUp(self):
            super(TestPublishableRecursiveForeignKey, self).setUp()
            self.page1 = Page.objects.create(slug='page1', title='page 1', content='some content')
            self.page2 = Page.objects.create(slug='page2', title='page 2', content='other content', parent=self.page1)
        
        def test_publish_parent(self):
            # this shouldn't publish the child page
            self.page1.publish()
            self.failUnless(self.page1.public)
            self.failIf(self.page1.public.parent)
            
            page2 = Page.objects.get(id=self.page2.id)
            self.failIf(page2.public)
        
        def test_publish_child_parent_already_published(self):
            self.page1.publish()
            self.page2.publish()

            self.failUnless(self.page1.public)
            self.failUnless(self.page2.public)

            self.failIf(self.page1.public.parent)
            self.failUnless(self.page2.public.parent)

            self.failIfEqual(self.page1, self.page2.public.parent)

            self.failUnlessEqual('/page1/', self.page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', self.page2.public.get_absolute_url())

        def test_publish_child_parent_not_already_published(self):
            self.page2.publish()
            
            page1 = Page.objects.get(id=self.page1.id)
            self.failUnless(page1.public)
            self.failUnless(self.page2.public)

            self.failIf(page1.public.parent)
            self.failUnless(self.page2.public.parent)

            self.failIfEqual(page1, self.page2.public.parent)

            self.failUnlessEqual('/page1/', self.page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', self.page2.public.get_absolute_url())

        def test_publish_repeated(self):
            self.page1.publish()
            self.page2.publish()
            
            self.page1.slug='main'
            self.page1.save()

            self.failUnlessEqual('/main/', self.page1.get_absolute_url())
            
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            self.failUnlessEqual('/page1/', page1.public.get_absolute_url())
            self.failUnlessEqual('/page1/page2/', page2.public.get_absolute_url())
            
            page1.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            self.failUnlessEqual('/main/', page1.public.get_absolute_url())
            self.failUnlessEqual('/main/page2/', page2.public.get_absolute_url())
            
            page1.slug='elsewhere'
            page1.save()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            page2.slug='meanwhile'
            page2.save()
            page2.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)
            
            # only page2 should be published, not page1, as page1 already published
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page2.publish_state)
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, page1.publish_state)

            self.failUnlessEqual('/main/', page1.public.get_absolute_url())
            self.failUnlessEqual('/main/meanwhile/', page2.public.get_absolute_url())

            page1.publish()
            page1 = Page.objects.get(id=self.page1.id)
            page2 = Page.objects.get(id=self.page2.id)

            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page2.publish_state)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, page1.publish_state)

            self.failUnlessEqual('/elsewhere/', page1.public.get_absolute_url())
            self.failUnlessEqual('/elsewhere/meanwhile/', page2.public.get_absolute_url())

        def test_publish_deletions(self):
            self.page1.publish()
            self.page2.publish()
            
            public = self.page2.public
            self.page2.delete()
            self.failUnlessEqual([public], list(Page.objects.deleted()))

            public.publish()
            self.failUnlessEqual([self.page1.public], list(Page.objects.published()))
            self.failUnlessEqual([], list(Page.objects.deleted()))

        def test_publish_reverse_fields(self):
            page_block = PageBlock.objects.create(page=self.page1, content='here we are')

            self.page1.publish()

            public = self.page1.public
            self.failUnless(public)
            
            blocks = list(public.pageblock_set.all())
            self.failUnlessEqual(1, len(blocks))
            self.failUnlessEqual(page_block.content, blocks[0].content)
        
        def test_publish_deletions_reverse_fields(self):
            page_block = PageBlock.objects.create(page=self.page1, content='here we are')

            self.page1.publish()
            public = self.page1.public
            self.failUnless(public)
           
            self.page1.delete()
            public = Page.objects.get(id=public.id)
            
            self.failUnlessEqual([public], list(Page.objects.deleted()))
            
            public.publish()
            self.failUnlessEqual([], list(Page.objects.deleted()))
            self.failUnlessEqual([], list(Page.objects.all()))
        
        def test_publish_reverse_fields_deleted(self):
            # make sure child elements get removed
            page_block = PageBlock.objects.create(page=self.page1, content='here we are')
            
            self.page1.publish()
            
            public = self.page1.public
            page_block = PageBlock.objects.get(id=page_block.id)
            page_block_public = page_block.public
            self.failIf(page_block_public is None)
            
            self.failUnlessEqual([page_block_public], list(public.pageblock_set.all()))
            
            # now delete the page block and publish the parent
            # to make sure that deletion gets copied over properly
            page_block.delete()
            page1 = Page.objects.get(id=self.page1.id)
            page1.publish()
            public = page1.public
            
            self.failUnlessEqual([], list(public.pageblock_set.all()))

        def test_publish_delections_with_non_publishable_children(self):
            self.page1.publish()

            public = self.page1.public
            comment = Comment.objects.create(page=public, comment='This is a comment')

            self.failUnlessEqual(1, Comment.objects.count())

            self.page1.delete()

            public = Page.objects.get(id=public.id)
            
            self.failUnlessEqual([public], list(Page.objects.deleted()))

            public.publish()
            self.failUnlessEqual([], list(Page.objects.deleted()))
            self.failUnlessEqual([], list(Page.objects.all()))
            self.failUnlessEqual([], list(Comment.objects.all()))

    class TestPublishableRecursiveManyToManyField(TransactionTestCase):

        def setUp(self):
            super(TestPublishableRecursiveManyToManyField, self).setUp()
            self.page = Page.objects.create(slug='page1', title='page 1', content='some content')
            self.author1 = Author.objects.create(name='author1', profile='a profile')
            self.author2 = Author.objects.create(name='author2', profile='something else')

        def test_publish_add_author(self):
            self.page.authors.add(self.author1)
            self.page.publish()
            self.failUnless(self.page.public)

            author1 = Author.objects.get(id=self.author1.id)
            self.failUnless(author1.public)
            self.failIfEqual(author1.id, author1.public.id)
            self.failUnlessEqual(author1.name, author1.public.name)
            self.failUnlessEqual(author1.profile, author1.public.profile)            

            self.failUnlessEqual([author1.public], list(self.page.public.authors.all()))

        def test_publish_repeated_add_author(self):
            self.page.authors.add(self.author1)
            self.page.publish()
            
            self.failUnless(self.page.public)

            self.page.authors.add(self.author2)
            author1 = Author.objects.get(id=self.author1.id)
            self.failUnlessEqual([author1.public], list(self.page.public.authors.all()))

            self.page.publish()
            author1 = Author.objects.get(id=self.author1.id)
            author2 = Author.objects.get(id=self.author2.id)
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

        def test_publish_clear_authors(self):
            self.page.authors.add(self.author1, self.author2)
            self.page.publish()

            author1 = Author.objects.get(id=self.author1.id)
            author2 = Author.objects.get(id=self.author2.id)
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

            self.page.authors.clear()
            self.failUnlessEqual([author1.public, author2.public], list(self.page.public.authors.order_by('name')))

            self.page.publish()
            self.failUnlessEqual([], list(self.page.public.authors.all()))

    class TestInfiniteRecursion(TransactionTestCase):
        
        def setUp(self):
            super(TestInfiniteRecursion, self).setUp()
            
            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2', parent=self.page1)
            self.page1.parent = self.page2
            self.page1.save()
        
        def test_publish_recursion_breaks(self):
            self.page1.publish() # this should simple run without an error

    class TestPublishableAdmin(TransactionTestCase):
        
        def setUp(self):
            super(TestPublishableAdmin, self).setUp()
            self.page1 = Page.objects.create(slug='page1', title='page 1')
            self.page2 = Page.objects.create(slug='page2', title='page 2')
            self.page1.publish()
            self.page2.publish()

            self.author1 = Author.objects.create(name='a1')
            self.author2 = Author.objects.create(name='a2')
            self.author1.publish()
            self.author2.publish()

            self.admin_site = AdminSite('Test Admin')
            
            class PageBlockInline(StackedInline):
                model = PageBlock

            class PageAdmin(PublishableAdmin):
                inlines = [PageBlockInline]

            self.page_admin = PageAdmin(Page, self.admin_site)

        def test_queryset(self):
            # make sure we only get back draft objects
            request = None
            
            self.failUnlessEqual(
                set([self.page1, self.page1.public, self.page2, self.page2.public]),
                set(Page.objects.all())
            )
            self.failUnlessEqual(
                set([self.page1, self.page2]),
                set(self.page_admin.queryset(request))
            )
        
        def test_get_actions_global_delete_replaced(self):
            from publish.actions import delete_selected
            
            request = None
            actions = self.page_admin.get_actions(request)
            
            
            self.failUnless('delete_selected' in actions)
            action, name, description = actions['delete_selected']
            self.failUnlessEqual(delete_selected, action)
            self.failUnlessEqual('delete_selected', name)
            self.failUnlessEqual(delete_selected.short_description, description)
        
        def test_formfield_for_foreignkey(self):
            # foreign key forms fields in admin
            # for publishable models should be filtered
            # to hide public object

            request = None
            parent_field = None
            for field in Page._meta.fields:
                if field.name == 'parent':
                    parent_field = field
                    break
            self.failUnless(parent_field)
            
            choice_field = self.page_admin.formfield_for_foreignkey(parent_field, request)
            self.failUnless(choice_field)
            self.failUnless(isinstance(choice_field, ModelChoiceField))

            self.failUnlessEqual(
                set([self.page1, self.page1.public, self.page2, self.page2.public]),
                set(Page.objects.all())
            )
            self.failUnlessEqual(
                set([self.page1, self.page2]),
                set(choice_field.queryset)
            )

        def test_formfield_for_manytomany(self):
            request = None
            authors_field = None
            for field in Page._meta.many_to_many:
                if field.name == 'authors':
                    authors_field = field
                    break
            self.failUnless(authors_field)

            choice_field = self.page_admin.formfield_for_manytomany(authors_field, request)
            self.failUnless(choice_field)
            self.failUnless(isinstance(choice_field, ModelMultipleChoiceField))

            self.failUnlessEqual(
                set([self.author1, self.author1.public, self.author2, self.author2.public]),
                set(Author.objects.all())
            )
            self.failUnlessEqual(
                set([self.author1, self.author2]),
                set(choice_field.queryset)
            )
        
        def test_has_change_permission(self):
            class dummy_request(object):
                method = 'GET'
                REQUEST = {}
                
                class user(object):
                    @classmethod
                    def has_perm(cls, permission):
                        return True

            self.failUnless(self.page_admin.has_change_permission(dummy_request))
            self.failUnless(self.page_admin.has_change_permission(dummy_request, self.page1))
            self.failIf(self.page_admin.has_change_permission(dummy_request, self.page1.public))

            # can view deleted public items
            self.page1.public.publish_state = Publishable.PUBLISH_DELETE
            self.failUnless(self.page_admin.has_change_permission(dummy_request, self.page1.public))

            # but cannot modify them
            dummy_request.method = 'POST'
            self.failIf(self.page_admin.has_change_permission(dummy_request, self.page1.public))
 
        def test_has_delete_permission(self):
            class dummy_request(object):
                method = 'GET'
                REQUEST = {}
                
                class user(object):
                    @classmethod
                    def has_perm(cls, permission):
                        return True

            self.failUnless(self.page_admin.has_delete_permission(dummy_request))
            self.failUnless(self.page_admin.has_delete_permission(dummy_request, self.page1))
            self.failIf(self.page_admin.has_delete_permission(dummy_request, self.page1.public))
        
        def test_change_view_normal(self):
            class dummy_request(object):
                method = 'GET'
                REQUEST = {}
                
                class user(object):
                    @classmethod
                    def has_perm(cls, permission):
                        return True

                    @classmethod
                    def get_and_delete_messages(cls):
                        return []
            
            response = self.page_admin.change_view(dummy_request, str(self.page1.id))
            self.failUnless(response is not None)
            self.failIf('deleted' in response.content)
        
        def test_change_view_not_deleted(self):
            class dummy_request(object):
                class user(object):
                    @classmethod
                    def has_perm(cls, permission):
                        return True
            
            try:
                self.page_admin.change_view(dummy_request, str(self.page1.public.id))
                fail()
            except Http404:
                pass

        def test_change_view_deleted(self):
            class dummy_request(object):
                method = 'GET'
                REQUEST = {}
                 
                class user(object):
                    @classmethod
                    def has_perm(cls, permission):
                        return True
                    
                    @classmethod
                    def get_and_delete_messages(cls):
                        return []
            
            public1 = self.page1.public
            self.page1.delete()

            response = self.page_admin.change_view(dummy_request, str(public1.id))
            self.failUnless(response is not None)
            self.failUnless('deleted' in response.content)

        def test_change_view_deleted_POST(self):
            class dummy_request(object):
                method = 'POST'
                        
            public1 = self.page1.public
            self.page1.delete()

            try:
                self.page_admin.change_view(dummy_request, str(public1.id))
                fail()
            except PermissionDenied:
                pass
     
    class TestPublishSelectedAction(TransactionTestCase):
        
        def setUp(self):
            super(TestPublishSelectedAction, self).setUp()
            self.fp1 = Page.objects.create(slug='fp1', title='FP1')
            self.fp2 = Page.objects.create(slug='fp2', title='FP2')
            self.fp3 = Page.objects.create(slug='fp3', title='FP3')

            self.admin_site = AdminSite('Test Admin')
            self.page_admin = PublishableAdmin(Page, self.admin_site)
            
            # override urls, so reverse works
            settings.ROOT_URLCONF=patterns('',
                ('^admin/', include(self.admin_site.urls)),
            )

        def test_publish_selected_confirm(self):
            pages = Page.objects.exclude(id=self.fp3.id)
            
            class dummy_request(object):
                POST = {}

                class user(object):
                    @classmethod
                    def has_perm(cls, *arg):
                        return True

                    @classmethod
                    def get_and_delete_messages(cls):
                        return []

            response = publish_selected(self.page_admin, dummy_request, pages)

            self.failIf(Page.objects.published().count() > 0)
            self.failUnless(response is not None)
            self.failUnlessEqual(200, response.status_code)

        def test_publish_selected_confirmed(self):
            pages = Page.objects.exclude(id=self.fp3.id)
            
            class dummy_request(object):
                POST = {'post': True}

                class user(object):
                    @classmethod
                    def has_perm(cls, *arg):
                        return True
        
                    class message_set(object):
                        @classmethod
                        def create(cls, message=None):
                            self._message = message
                    

            response = publish_selected(self.page_admin, dummy_request, pages)
                        

            self.failUnlessEqual(2, Page.objects.published().count())
            self.failUnless( getattr(self, '_message', None) is not None )
            self.failUnless( response is None )

        def test_convert_all_published_to_html(self):
            self.admin_site.register(Page, PublishableAdmin)

            all_published = NestedSet()
            
            page = Page.objects.create(slug='here', title='title')
            block = PageBlock.objects.create(page=page, content='stuff here')

            all_published.add(page) 
            all_published.add(block, parent=page)

            converted = _convert_all_published_to_html(self.page_admin, all_published)

            expected = [u'<a href="../../publish/page/%d/">Page: Page object (Changed - not yet published)</a>' % page.id, [u'Page block: PageBlock object (Changed - not yet published)']]

            self.failUnlessEqual(expected, converted)
        
        def test_publish_status(self):
            self.failUnlessEqual(' (Changed - not yet published)', _publish_status(self.fp1))
            self.fp1.publish()
            self.failUnlessEqual('', _publish_status(self.fp1))
            self.fp1.save()
            self.failUnlessEqual(' (Changed)', _publish_status(self.fp1))
            
            public = self.fp1.public
            self.fp1.delete()
            public = Page.objects.get(id=public.id)
            self.failUnlessEqual(' (To be deleted)', _publish_status(public))

        def test_publish_selected_does_not_have_permission(self):
            pages = Page.objects.exclude(id=self.fp3.id)
            
            class dummy_request(object):
                POST = {}

                class user(object):
                    @classmethod
                    def has_perm(cls, *arg):
                        return False 

                    @classmethod
                    def get_and_delete_messages(cls):
                        return []
            try:
                publish_selected(self.page_admin, dummy_request, pages)
                self.fail()
            except PermissionDenied:
                pass
            
            self.failIf(Page.objects.published().count() > 0)
        
        def test_publish_selected_does_not_have_related_permission(self):
            # check we can't publish when we don't have permission
            # for a related model (in this case authors)
            self.admin_site.register(Author, PublishableAdmin)

            author = Author.objects.create(name='John')
            self.fp1.authors.add(author)

            pages = Page.objects.draft()

            class dummy_request(object):
                POST = { 'post': True }

                class user(object):
                    @classmethod
                    def has_perm(cls, perm):
                        return perm != 'publish.publish_author'
            
            try:
                publish_selected(self.page_admin, dummy_request, pages)
                self.fail()
            except PermissionDenied:
                pass
            
            self.failIf(Page.objects.published().count() > 0)

        
    class TestDeleteSelected(TransactionTestCase):
        
        def setUp(self):
            super(TestDeleteSelected, self).setUp()
            self.fp1 = FlatPage.objects.create(url='/fp1', title='FP1')
            self.fp2 = FlatPage.objects.create(url='/fp2', title='FP2')
            self.fp3 = FlatPage.objects.create(url='/fp3', title='FP3')
            
            self.fp1.publish()
            self.fp2.publish()
            self.fp3.publish()
            
            self.admin_site = AdminSite('Test Admin')
            self.page_admin = PublishableAdmin(FlatPage, self.admin_site)
            
            # override urls, so reverse works
            settings.ROOT_URLCONF=patterns('',
                ('^admin/', include(self.admin_site.urls)),
            )
        
        def test_delete_selected_check_cannot_delete_public(self):
            # delete won't work (via admin) for public instances
            request = None
            try:
                delete_selected(self.page_admin, request, FlatPage.objects.published())
                fail()
            except PermissionDenied:
                pass
        
        def test_delete_selected(self):
            class dummy_request(object):
                POST = { }
                
                class user(object):
                    @classmethod
                    def has_perm(cls, *arg):
                        return True
                    
                    @classmethod
                    def get_and_delete_messages(cls):
                        return []
            
            response = delete_selected(self.page_admin, dummy_request, FlatPage.objects.draft())
            self.failUnless(response is not None)

    class TestManyToManyThrough(TransactionTestCase):
        
        def setUp(self):
            super(TestManyToManyThrough, self).setUp()
            self.page = Page.objects.create(slug='p1', title='P 1')
            self.tag1 = Tag.objects.create(slug='tag1', title='Tag 1')
            self.tag2 = Tag.objects.create(slug='tag2', title='Tag 2')
            PageTagOrder.objects.create(page=self.page, tag=self.tag1, tag_order=2)
            PageTagOrder.objects.create(page=self.page, tag=self.tag2, tag_order=1)
            
        def test_publish_copies_tags(self):
            self.page.publish()
            
            self.failUnlessEqual(set([self.tag1, self.tag2]), set(self.page.public.tags.all()))

    class TestPublishFunction(TransactionTestCase):
    
        def setUp(self):
            super(TestPublishFunction, self).setUp()
            self.page = Page.objects.create(slug='page', title='Page')

        def test_publish_function_invoked(self):
            # check we can override default copy behaviour            

            from datetime import datetime

            pub_date = datetime(2000, 1, 1)
            update_pub_date.pub_date = pub_date

            self.failIfEqual(pub_date, self.page.pub_date)
            
            self.page.publish()
            self.failIfEqual(pub_date, self.page.pub_date)
            self.failUnlessEqual(pub_date, self.page.public.pub_date)
