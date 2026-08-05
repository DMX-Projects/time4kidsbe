from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, TestCase

from accounts.crm_zones import filter_qs_by_zone_or_assigned
from accounts.models import User
from enquiries.crm_api import campaign_channel_api_key, effective_source_bucket_key, should_include_in_google_bucket
from enquiries.emails import lead_source_label_for_crm_lead
from enquiries.models import CrmLead, CrmLeadSource


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

    def test_wb_meta_lead_bucket_is_generic_meta_for_non_ants_viewers(self):
        lead = SimpleNamespace(
            source="lp_wb",
            state="West Bengal",
            utm_source="facebook_lead_ads",
            utm_medium="cpc",
            landing_page_url="https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads",
            gclid="",
        )

        self.assertEqual(effective_source_bucket_key(lead), "july_meta")

    def test_dashboard_bucket_mapping_for_wb_meta_leads(self):
        self.assertEqual(
            campaign_channel_api_key("lp_wb", "https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads", "West Bengal"),
            "july_meta",
        )

    def test_wb_meta_label_is_generic_meta_for_non_ants_viewers(self):
        lead = SimpleNamespace(
            source="lp_wb",
            state="West Bengal",
            utm_source="facebook_lead_ads",
            utm_medium="cpc",
            landing_page_url="https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads",
            gclid="",
        )
        self.assertEqual(lead_source_label_for_crm_lead(lead), "META")

    def test_ants_agency_viewer_keeps_ants_meta_bucket(self):
        user = SimpleNamespace(email="ants.agency@gmail.com")
        self.assertEqual(
            campaign_channel_api_key(
                "lp_wb",
                "https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads",
                "West Bengal",
                user=user,
            ),
            "ants_meta",
        )

    def test_ants_agency_viewer_keeps_ants_meta_label(self):
        lead = SimpleNamespace(
            source="lp_wb",
            state="West Bengal",
            utm_source="facebook_lead_ads",
            utm_medium="cpc",
            landing_page_url="https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads",
            gclid="",
        )
        self.assertEqual(lead_source_label_for_crm_lead(lead, user=SimpleNamespace(email="ants.agency@gmail.com")), "Ants_Meta")


class RestrictedAgencyViewerTests(TestCase):
    def test_agency_viewer_keeps_its_allowed_rows_under_strict_validation(self):
        viewer = User.objects.create_user(
            email="ants.agency@gmail.com",
            password="testpass123",
            role="CRM",
            full_name="Ants Agency",
            crm_states="West Bengal",
        )
        lead = CrmLead.objects.create(
            full_name="Strict Validation Lead",
            mobile="9999999999",
            email="strict@example.com",
            state="West Bengal",
            city="Kolkata",
            source=CrmLeadSource.LP_WB,
            status="untouched",
            raw_payload={"crm_handoff_hidden_from": str(viewer.pk)},
        )

        request = RequestFactory().get('/crm-admin')
        request.user = viewer

        qs = CrmLead.objects.filter(pk=lead.pk)
        result = filter_qs_by_zone_or_assigned(qs, __import__('django.db.models').db.models.Q(state__iexact='West Bengal'), request)

        self.assertEqual(result.count(), 1)
