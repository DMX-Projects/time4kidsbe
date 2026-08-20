from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from accounts.crm_zones import filter_qs_by_zone_or_assigned
from accounts.models import User
from enquiries.crm_api import campaign_channel_api_key, effective_source_bucket_key, should_include_in_google_bucket
from enquiries.emails import lead_source_label_for_crm_lead
from enquiries.meta_leads import (
    _field_map,
    _first_tracking_id,
    form_name_to_utm_token,
    is_allowed_meta_form,
    meta_instant_form_utm_fields,
    parse_utm_query_string,
    strip_meta_export_prefix,
)
from enquiries.meta_capi import (
    build_crm_event,
    event_name_for_status,
    hash_sha256,
    is_qualified_capi_status,
    meta_leadgen_id_from_lead,
    normalize_phone_e164_digits,
    send_crm_stage_event,
    should_upload_capi_event,
)
from enquiries.models import CrmLead, CrmLeadSource


class MetaInstantFormUtmTests(SimpleTestCase):
    def test_form_name_to_utm_token_matches_agency_example(self):
        self.assertEqual(
            form_name_to_utm_token("BCWW TK Andhra Pradesh All Interest P1"),
            "BCWW_TK_Andhra_Pradesh_All_Interest_P1",
        )

    def test_meta_instant_form_utm_uses_form_name_when_nothing_else_passed(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Andhra Pradesh All Interest P1",
        )
        self.assertEqual(utm["utm_source"], "facebook_lead_ads")
        self.assertEqual(utm["utm_medium"], "BCWW_TK_Andhra_Pradesh_All_Interest_P1")
        self.assertEqual(utm["utm_campaign"], "BCWW_TK_Andhra_Pradesh_All_Interest_P1")
        self.assertEqual(utm["utm_content"], "")

    def test_meta_instant_form_utm_captures_passed_values_only(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Andhra Pradesh All Interest P1",
            fields={
                "utm_medium": "BCWW_TK_Andhra_Pradesh_All_Interest_P1",
                "utm_campaign": "BCWW_TK_Andhra_Pradesh_All_Interest_P1",
                "utm_content": "dm",
            },
        )
        self.assertEqual(utm["utm_source"], "facebook_lead_ads")
        self.assertEqual(utm["utm_medium"], "BCWW_TK_Andhra_Pradesh_All_Interest_P1")
        self.assertEqual(utm["utm_campaign"], "BCWW_TK_Andhra_Pradesh_All_Interest_P1")
        self.assertEqual(utm["utm_content"], "dm")

    def test_utm_content_from_ad_url_tags(self):
        tags = (
            "utm_source=facebook_lead_ads"
            "&utm_medium=BCWW_TK_Andhra_Pradesh_All_Interest_P1"
            "&utm_campaign=BCWW_TK_Andhra_Pradesh_All_Interest_P1"
            "&utm_content=dm"
        )
        parsed = parse_utm_query_string(tags)
        self.assertEqual(parsed.get("utm_content"), "dm")
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Andhra Pradesh All Interest P1",
            ad_url_tags=tags,
        )
        self.assertEqual(utm["utm_content"], "dm")
        self.assertEqual(utm["utm_source"], "facebook_lead_ads")

    def test_utm_content_from_form_tracking_parameters(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Andhra Pradesh All Interest P1",
            form_tracking={"utm_content": "dm"},
        )
        self.assertEqual(utm["utm_content"], "dm")

    def test_ad_id_maps_to_utm_content_for_any_instant_form(self):
        for form_name in (
            "BCWW TK Tamil Nadu All Interest P1",
            "BCWW TK Karnataka RMK P1",
            "BCWW TK Andhra Pradesh LLK Ex P1",
            "BCWW TK Telangana Income P1",
            "BCWW TK Maharashtra All Interest Ex P1",
            "BCWW TK Kerala All Interest Ex P1 - R1",
        ):
            utm = meta_instant_form_utm_fields(
                form_name=form_name,
                ad_id="ag:120246896442180772",
            )
            self.assertEqual(utm["utm_content"], "120246896442180772", form_name)

    def test_instant_form_csv_names_map_to_utm_columns(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Kerala All Interest Ex P1 - R1",
            campaign_name="Meta_Lead_Gen_Ex_P1_Kerala",
            ad_id="ag:120246896442180772",
            ad_name="Meta_Kerala_All Interest_Ex_P1 - Join without CTA",
            adset_name="Meta_Kerala_All Interest_Ex_P1",
        )
        self.assertEqual(utm["utm_source"], "facebook_lead_ads")
        self.assertEqual(utm["utm_medium"], "BCWW_TK_Kerala_All_Interest_Ex_P1_R1")
        self.assertEqual(utm["utm_campaign"], "Meta_Lead_Gen_Ex_P1_Kerala")
        self.assertEqual(utm["utm_content"], "120246896442180772")
        self.assertEqual(utm["utm_term"], "Meta_Kerala_All Interest_Ex_P1")

    def test_explicit_utm_content_wins_over_ad_id(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Kerala LLK Ex P1 - R1",
            ad_id="120246896442180772",
            form_tracking={"utm_content": "dm"},
        )
        self.assertEqual(utm["utm_content"], "dm")

    def test_inline_form_params_capture_ad_id_from_field_data(self):
        mapped = _field_map(
            [
                {"name": "full_name", "values": ["Ada"]},
                {"name": "ad_id", "values": ["ag:120246896442180772"]},
                {"name": "ad_name", "values": ["Meta_Kerala_All Interest_Ex_P1 - Join without CTA"]},
                {"name": "adset_id", "values": ["as:120246827546650772"]},
                {"name": "adset_name", "values": ["Meta_Kerala_All Interest_Ex_P1"]},
                {"name": "campaign_id", "values": ["c:120246827546700772"]},
                {"name": "campaign_name", "values": ["Meta_Lead_Gen_Ex_P1_Kerala"]},
                {"name": "form_id", "values": ["f:2660208977769920"]},
                {"name": "form_name", "values": ["BCWW TK Kerala All Interest Ex P1 - R1"]},
                {"name": "platform", "values": ["ig"]},
            ]
        )
        self.assertEqual(mapped["ad_id"], "ag:120246896442180772")
        self.assertEqual(mapped["ad_name"], "Meta_Kerala_All Interest_Ex_P1 - Join without CTA")
        self.assertEqual(mapped["campaign_id"], "c:120246827546700772")
        self.assertEqual(mapped["form_id"], "f:2660208977769920")
        self.assertEqual(mapped["platform"], "ig")
        self.assertEqual(_first_tracking_id(mapped["ad_id"]), "120246896442180772")
        self.assertEqual(_first_tracking_id(mapped["adset_id"]), "120246827546650772")
        self.assertEqual(_first_tracking_id(mapped["campaign_id"]), "120246827546700772")
        self.assertEqual(_first_tracking_id(mapped["form_id"]), "2660208977769920")
        self.assertEqual(strip_meta_export_prefix("l:27933512212942750"), "27933512212942750")
        self.assertEqual(strip_meta_export_prefix("p:+917306874088"), "+917306874088")
        self.assertNotIn("ad_id", mapped.get("extra_qa", ""))
        self.assertNotIn("120246896442180772", mapped.get("extra_qa", ""))

    def test_inline_form_params_ignore_unresolved_macros(self):
        mapped = _field_map([{"name": "ad_id", "values": ["{{ad.id}}"]}])
        self.assertNotIn("ad_id", mapped)
        self.assertEqual(_first_tracking_id("", "{{ad.id}}", "12021800111"), "12021800111")


class MetaFormAllowlistTests(SimpleTestCase):
    @override_settings(META_LEADS_FORM_NAMES="", META_LEADS_FORM_PREFIXES="BCWW TK", META_LEADS_FORM_IDS="")
    def test_prefix_mode_captures_new_bcww_campaign_forms(self):
        self.assertTrue(is_allowed_meta_form(form_name="BCWW TK Tamil Nadu All Interest P1"))
        self.assertTrue(is_allowed_meta_form(form_name="BCWW TK Tamil Nadu All Interest P1 - R2"))
        self.assertTrue(is_allowed_meta_form(form_name="BCWW TK Kerala LLK Ex P1 - R1"))
        self.assertFalse(is_allowed_meta_form(form_name="TIME Kids Old City Form"))
        self.assertFalse(is_allowed_meta_form(form_name="Ants WB Form"))
        self.assertFalse(is_allowed_meta_form(form_name=""))


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

    def test_wb_meta_lead_bucket_is_ants_meta_for_all_users(self):
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

    def test_wb_meta_label_is_ants_meta_for_all_users(self):
        lead = SimpleNamespace(
            source="lp_wb",
            state="West Bengal",
            utm_source="facebook_lead_ads",
            utm_medium="cpc",
            landing_page_url="https://www.timekidspreschools.in/timekids-lp-wb/?utm_source=facebook_lead_ads",
            gclid="",
        )
        self.assertEqual(lead_source_label_for_crm_lead(lead), "Ants_Meta")

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


class ApTsEqualShareAssignTests(TestCase):
    def setUp(self):
        from accounts.models import UserRole
        from enquiries.crm_users import suggest_assignee_for_geo, rebalance_ap_ts_equal_share

        self.suggest_assignee_for_geo = suggest_assignee_for_geo
        self.rebalance_ap_ts_equal_share = rebalance_ap_ts_equal_share
        self.harshit = User.objects.create_user(
            email="harshit@timekidspreschools.com",
            password="testpass123",
            role=UserRole.CRM,
            full_name="Harshit Katare",
            crm_states="Andhra Pradesh, Telangana",
        )
        self.sai = User.objects.create_user(
            email="saikishore@timekidspreschools.com",
            password="testpass123",
            role=UserRole.CRM,
            full_name="Sai Kishore",
            crm_states="Andhra Pradesh, Telangana",
        )
        self.jayaraj = User.objects.create_user(
            email="jayaraj@timekidspreschools.com",
            password="testpass123",
            role=UserRole.CRM,
            full_name="M. Jayaraj",
            crm_states="Tamil Nadu",
        )
        self.sivaraman = User.objects.create_user(
            email="sivaraman@timekidspreschools.com",
            password="testpass123",
            role=UserRole.CRM,
            full_name="Sivaraman",
            crm_states="Tamil Nadu",
        )

    def _assign(self, user, *, state, city, status="untouched"):
        return CrmLead.objects.create(
            full_name=f"Lead {user.id} {city}",
            mobile="9999999999",
            email="lead@example.com",
            state=state,
            city=city,
            source=CrmLeadSource.JULY_META,
            status=status,
            assigned_user=user,
        )

    def test_hyd_and_andra_alternate_between_sai_and_harshit(self):
        first = self.suggest_assignee_for_geo(
            "Telangana", "Hyderabad", pipeline="franchise"
        )
        self.assertIsNotNone(first)
        self._assign(first, state="Telangana", city="Hyderabad")

        second = self.suggest_assignee_for_geo(
            "Andhra Pradesh", "Vijayawada", pipeline="franchise"
        )
        self.assertIsNotNone(second)
        self.assertNotEqual(first.id, second.id)
        self.assertSetEqual(
            {first.email.lower(), second.email.lower()},
            {"harshit@timekidspreschools.com", "saikishore@timekidspreschools.com"},
        )

        self._assign(second, state="Andhra Pradesh", city="Vijayawada")
        third = self.suggest_assignee_for_geo(
            "Telangana", "Hyderabad", pipeline="franchise", ignore_city=True
        )
        self.assertEqual(third.id, first.id)

    def test_tamil_nadu_still_goes_to_first_handler_not_round_robin(self):
        for _ in range(3):
            self._assign(self.jayaraj, state="Tamil Nadu", city="Chennai")
        picked = self.suggest_assignee_for_geo(
            "Tamil Nadu", "Chennai", pipeline="franchise"
        )
        self.assertEqual(picked.id, self.jayaraj.id)

    def test_rebalance_moves_untouched_only(self):
        for _ in range(4):
            self._assign(self.harshit, state="Telangana", city="Hyderabad")
        self._assign(self.harshit, state="Andhra Pradesh", city="Guntur", status="follow_up")
        result = self.rebalance_ap_ts_equal_share(dry_run=False)
        self.assertEqual(result["moved"], 2)
        self.assertEqual(
            CrmLead.objects.filter(assigned_user=self.harshit).count(), 3
        )
        self.assertEqual(
            CrmLead.objects.filter(assigned_user=self.sai).count(), 2
        )
        self.assertEqual(
            CrmLead.objects.filter(
                assigned_user=self.harshit, status="follow_up"
            ).count(),
            1,
        )


class MetaCapiPayloadTests(SimpleTestCase):
    def test_phone_hash_uses_india_country_code(self):
        digits = normalize_phone_e164_digits("9876543210")
        self.assertEqual(digits, "919876543210")
        self.assertEqual(hash_sha256(digits), hash_sha256("919876543210"))

    def test_event_name_maps_initial_and_crm_stages(self):
        self.assertEqual(event_name_for_status("untouched"), "Lead")
        self.assertEqual(event_name_for_status("follow_up"), "Follow-up")
        self.assertEqual(event_name_for_status("visited_school"), "Visited the school")
        self.assertEqual(event_name_for_status("converted_admission"), "Converted to Admission")

    def test_build_crm_event_has_required_conversion_leads_fields(self):
        lead = SimpleNamespace(
            pk=12,
            status="follow_up",
            full_name="Anita Sharma",
            mobile="9876543210",
            email="anita@example.com",
            city="Hyderabad",
            state="Telangana",
            landing_page_url="",
            created_at=None,
            raw_payload={"meta_leadgen_id": "1234567890123456"},
        )
        event = build_crm_event(lead)
        self.assertIsNotNone(event)
        self.assertEqual(event["event_name"], "Follow-up")
        self.assertEqual(event["action_source"], "system_generated")
        self.assertEqual(event["custom_data"]["event_source"], "crm")
        self.assertEqual(event["custom_data"]["lead_event_source"], "TIME Kids CRM")
        self.assertEqual(event["user_data"]["lead_id"], 1234567890123456)
        self.assertEqual(event["user_data"]["em"], [hash_sha256("anita@example.com")])
        self.assertEqual(event["user_data"]["ph"], [hash_sha256("919876543210")])

    @override_settings(META_CAPI_ACCESS_TOKEN="test-token", META_CAPI_DATASET_ID="1502626011898766")
    def test_send_skips_non_instant_form_leads(self):
        lead = SimpleNamespace(pk=1, status="untouched", raw_payload={})
        result = send_crm_stage_event(lead)
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result.get("reason"), "not_meta_instant_form")

    def test_leadgen_id_reader(self):
        lead = SimpleNamespace(raw_payload={"meta_leadgen_id": " 9988776655443322 "})
        self.assertEqual(meta_leadgen_id_from_lead(lead), "9988776655443322")

    def test_only_qualified_statuses_are_sent(self):
        self.assertFalse(is_qualified_capi_status("untouched"))
        self.assertFalse(is_qualified_capi_status("not_answering_calls"))
        self.assertFalse(is_qualified_capi_status("not_interested"))
        self.assertFalse(is_qualified_capi_status("wrong_enquiry"))
        self.assertTrue(is_qualified_capi_status("follow_up"))
        self.assertTrue(is_qualified_capi_status("hot"))
        self.assertTrue(is_qualified_capi_status("converted_agreement_signed"))
        self.assertTrue(should_upload_capi_event("untouched", event_name="Lead"))
        self.assertFalse(should_upload_capi_event("wrong_enquiry", event_name="Lead"))
        self.assertFalse(should_upload_capi_event("untouched", event_name="Follow-up"))

    @override_settings(META_CAPI_ACCESS_TOKEN="test-token", META_CAPI_DATASET_ID="1502626011898766")
    def test_send_skips_unqualified_status(self):
        lead = SimpleNamespace(
            pk=1,
            status="wrong_enquiry",
            raw_payload={"meta_leadgen_id": "1234567890123456"},
        )
        result = send_crm_stage_event(lead)
        self.assertTrue(result.get("skipped"))
        self.assertEqual(result.get("reason"), "not_qualified_status")
