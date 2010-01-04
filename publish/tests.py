from django.conf import settings
 
if getattr(settings, 'TESTING_PUBLISH', False):
    from django.test import TransactionTestCase
    from publish.models import Publishable, FlatPage

    class TestBasicPublishable(TransactionTestCase):
        
        def setUp(self):
            super(TestBasicPublishable, self).setUp()
            self.flat_page = FlatPage()

        def test_save_marks_changed(self):
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save(mark_changed=False)
            self.failUnlessEqual(Publishable.PUBLISH_DEFAULT, self.flat_page.publish_state)
            self.flat_page.save()
            self.failUnlessEqual(Publishable.PUBLISH_CHANGED, self.flat_page.publish_state)

