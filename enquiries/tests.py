from types import SimpleNamespace

from django.test import SimpleTestCase

from enquiries.crm_api import campaign_channel_api_key, effective_source_bucket_key, should_include_in_google_bucket


class CrmGoogleBucketTests(SimpleTestCase):
    def test_wb_meta_lead_is_not_counted_as_google(self):
        lead = SimpleNamespace(
            source="lp_wb",
            utm_source="facebook_lead_ads",
            utm_medium="cpc",
            landing_page_url="https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads",
            gclid="",
        )

        self.assertFalse(should_include_in_google_bucket(lead))

    def test_google_lp_lead_still_counts_as_google(self):
        lead = SimpleNamespace(
            source="july_lp",
            utm_source="google",
            utm_medium="cpc",
            landing_page_url="https://www.timekidspreschools.in/?gclid=ABCD123",
            gclid="ABCD123",
        )

        self.assertTrue(should_include_in_google_bucket(lead))

    def test_wb_meta_lead_bucket_is_ants_meta(self):
        lead = SimpleNamespace(
            source="lp_wb",
            state="West Bengal",
            utm_source="facebook_lead_ads",
            utm_medium="cpc",
            landing_page_url="https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads",
            gclid="",
        )

        self.assertEqual(effective_source_bucket_key(lead), "ants_meta")

    def test_dashboard_bucket_mapping_for_wb_meta_leads(self):
        self.assertEqual(
            campaign_channel_api_key("lp_wb", "https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads", "West Bengal"),
            "ants_meta",
        )
