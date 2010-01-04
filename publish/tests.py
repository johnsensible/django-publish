from django.conf import settings
 
if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase
    from publish.models import Publishable, FlatPage

    class TestBasicPublishable(TransactionTestCase):
        
        def setUp(self):
            super(TestBasicPublishable, self).setUp()
            self.flat_page = FlatPage()
            self.flat_page.url = '/my-page/'
            self.flat_page.title = 'my page'
            self.flat_page.content = 'here is some content'
            self.flat_page.enable_comments = False
            self.flat_page.registration_required = True


        def test_save_marks_changed(self):
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save(mark_changed=False)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)
        
        def test_publish_check_is_not_public(self):
            try:
                self.flat_page.is_public = True
                self.flat_page.publish()
                self.fail("Should not be able to publish public models")
            except ValueError:
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

