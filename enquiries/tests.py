from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from accounts.crm_zones import filter_qs_by_zone_or_assigned
from accounts.models import User
from enquiries.crm_api import (
    _ants_crm_lead_q,
    _apply_agency_filter_to_crm_qs,
    _filter_crm_qs,
    _filter_landing_qs,
    campaign_channel_api_key,
    effective_source_bucket_key,
    should_include_in_google_bucket,
    unified_lead_detail,
    unified_leads_page,
    agency_lead_report_data,
)
from enquiries.crm_users import resolve_notify_lead_kind
from enquiries.emails import lead_source_label_for_crm_lead
from enquiries.meta_leads import (
    _field_map,
    _first_tracking_id,
    extract_url_tags_from_ad_graph,
    form_name_to_utm_token,
    is_allowed_meta_form,
    meta_instant_form_utm_fields,
    normalize_meta_city,
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
from enquiries.models import CrmLead, CrmLeadSource, Enquiry, EnquiryType, KidsEnquiry


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

    def test_ad_id_is_not_used_as_utm_content(self):
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
            self.assertEqual(utm["utm_content"], "", form_name)

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
        self.assertEqual(utm["utm_content"], "")
        self.assertEqual(utm["utm_term"], "Meta_Kerala_All Interest_Ex_P1")

    def test_explicit_utm_content_wins_over_ad_id(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Kerala LLK Ex P1 - R1",
            ad_id="120246896442180772",
            form_tracking={"utm_content": "dm"},
        )
        self.assertEqual(utm["utm_content"], "dm")

    def test_utm_content_keeps_any_campaign_assigned_value(self):
        for value in ("dm_plain", "dm", "video", "carousel"):
            utm = meta_instant_form_utm_fields(
                form_name="BCWW TK Kerala LLK Ex P1 - R1",
                ad_id="120246896442180772",
                form_tracking={"utm_content": value},
            )
            self.assertEqual(utm["utm_content"], value)

    def test_url_tags_utm_content_wins_over_ad_id(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Kerala LLK Ex P1 - R1",
            ad_id="120246896442180772",
            ad_url_tags="utm_content=dm_plain",
        )
        self.assertEqual(utm["utm_content"], "dm_plain")

    def test_utm_content_matching_ad_id_is_ignored(self):
        utm = meta_instant_form_utm_fields(
            form_name="BCWW TK Kerala LLK Ex P1 - R1",
            ad_id="ag:120246896442180772",
            form_tracking={"utm_content": "120246896442180772"},
        )
        self.assertEqual(utm["utm_content"], "")

    def test_extract_url_tags_from_ad_creative_graph(self):
        self.assertEqual(
            extract_url_tags_from_ad_graph({"url_tags": "utm_content=dm_plain"}),
            "utm_content=dm_plain",
        )
        self.assertEqual(
            extract_url_tags_from_ad_graph(
                {"creative": {"url_tags": "utm_content=video"}}
            ),
            "utm_content=video",
        )
        self.assertEqual(
            extract_url_tags_from_ad_graph(
                {
                    "creative": {
                        "object_story_spec": {
                            "link_data": {"url_tags": "utm_content=carousel"}
                        }
                    }
                }
            ),
            "utm_content=carousel",
        )

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


class WestBengalInstantFormMappingTests(SimpleTestCase):
    def test_wb_form_names_are_allowed_by_bcww_prefix(self):
        self.assertTrue(is_allowed_meta_form(form_name="BCWW TK West Bengal Income P1"))
        self.assertTrue(is_allowed_meta_form(form_name="BCWW TK West Bengal Real Estate P1"))

    def test_wb_free_text_cities_normalize(self):
        self.assertEqual(normalize_meta_city("Newtown .Kolkata")[0], "Kolkata")
        self.assertEqual(normalize_meta_city("Cooch Beharwest")[0], "Cooch Behar")
        self.assertEqual(normalize_meta_city("Payal Shah West Bengal Siliguri")[0], "Siliguri")
        self.assertEqual(normalize_meta_city("WB")[0], "Kolkata")


class AntsWestBengalInstantFormVisibilityTests(TestCase):
    def test_ants_scope_includes_wb_instant_forms_and_lp(self):
        instant = CrmLead.objects.create(
            full_name="WB Instant Form Lead",
            mobile="9000000001",
            email="wb.instant@example.com",
            state="West Bengal",
            city="Kolkata",
            source=CrmLeadSource.JULY_META,
            status="untouched",
            raw_payload={"meta_form_name": "BCWW TK West Bengal Income P1"},
        )
        lp = CrmLead.objects.create(
            full_name="WB LP Lead",
            mobile="9000000002",
            email="wb.lp@example.com",
            state="West Bengal",
            city="Kolkata",
            source=CrmLeadSource.LP_WB,
            status="untouched",
        )
        other = CrmLead.objects.create(
            full_name="Kerala Instant Form Lead",
            mobile="9000000003",
            email="kl.instant@example.com",
            state="Kerala",
            city="Ernakulam",
            source=CrmLeadSource.JULY_META,
            status="untouched",
        )

        visible = set(
            CrmLead.objects.filter(_ants_crm_lead_q()).values_list("id", flat=True)
        )
        self.assertIn(instant.id, visible)
        self.assertIn(lp.id, visible)
        self.assertNotIn(other.id, visible)


class BcwwAgencyFilterWestBengalInstantFormTests(TestCase):
    def _leads(self):
        instant = CrmLead.objects.create(
            full_name="BCWW WB Inline Form",
            mobile="9000000011",
            email="bcww.wb@example.com",
            state="West Bengal",
            city="Kolkata",
            source=CrmLeadSource.JULY_META,
            status="untouched",
            raw_payload={"meta_form_name": "BCWW TK West Bengal Income P1"},
        )
        lp = CrmLead.objects.create(
            full_name="Ants WB LP",
            mobile="9000000012",
            email="ants.lp@example.com",
            state="West Bengal",
            city="Kolkata",
            source=CrmLeadSource.LP_WB,
            status="untouched",
        )
        kerala = CrmLead.objects.create(
            full_name="BCWW Kerala Inline Form",
            mobile="9000000013",
            email="bcww.kl@example.com",
            state="Kerala",
            city="Ernakulam",
            source=CrmLeadSource.JULY_META,
            status="untouched",
        )
        return instant, lp, kerala

    def test_superadmin_bcww_filter_includes_wb_inline_forms(self):
        instant, lp, kerala = self._leads()
        admin = User.objects.create_user(
            email="crm.admin@timekidspreschools.com",
            password="testpass123",
            role="CRM",
            full_name="CRM Admin",
        )
        request = RequestFactory().get("/crm-admin", {"agency": "bcww"})
        request.user = admin

        visible = set(
            _apply_agency_filter_to_crm_qs(CrmLead.objects.all(), request).values_list("id", flat=True)
        )
        self.assertIn(instant.id, visible)
        self.assertIn(kerala.id, visible)
        self.assertNotIn(lp.id, visible)

    def test_superadmin_ants_filter_is_lp_only(self):
        instant, lp, kerala = self._leads()
        admin = User.objects.create_user(
            email="crm.admin@timekidspreschools.com",
            password="testpass123",
            role="CRM",
            full_name="CRM Admin",
        )
        request = RequestFactory().get("/crm-admin", {"agency": "ants"})
        request.user = admin

        visible = set(
            _apply_agency_filter_to_crm_qs(CrmLead.objects.all(), request).values_list("id", flat=True)
        )
        self.assertIn(lp.id, visible)
        self.assertNotIn(instant.id, visible)
        self.assertNotIn(kerala.id, visible)


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


class BcwwCityLandingVisibilityTests(TestCase):
    def _users(self):
        bcww = User.objects.create_user(
            email="bcwebwise.agency@gmail.com",
            password="testpass123",
            role="CRM",
            full_name="Bcwebwise Agency",
            crm_states="Tamil Nadu,Karnataka,Andhra Pradesh,Kerala,Telangana,Maharashtra",
        )
        ants = User.objects.create_user(
            email="ants.agency@gmail.com",
            password="testpass123",
            role="CRM",
            full_name="Ants Agency",
            crm_states="West Bengal",
        )
        return bcww, ants

    def _landing(self, **kwargs):
        defaults = dict(
            name="Chennai Landing Lead",
            mobile="9000000101",
            mobileno="9000000101",
            email="chennai.lp@example.com",
            state="Tamil Nadu",
            city="Chennai",
            location="T.I.M.E. Kids Anna Nagar",
            enquiry_type="Admission Enquiry",
            source="Google",
        )
        defaults.update(kwargs)
        return KidsEnquiry.objects.create(**defaults)

    def test_bcww_sees_city_landing_leads_ants_does_not(self):
        bcww, ants = self._users()
        chennai = self._landing()
        kolkata = self._landing(
            name="Kolkata Landing Lead",
            mobile="9000000102",
            mobileno="9000000102",
            email="kolkata.lp@example.com",
            state="West Bengal",
            city="Kolkata",
        )

        bcww_req = RequestFactory().get("/crm-admin")
        bcww_req.user = bcww
        ants_req = RequestFactory().get("/crm-admin")
        ants_req.user = ants

        bcww_ids = set(_filter_landing_qs(bcww_req).values_list("id", flat=True))
        ants_ids = set(_filter_landing_qs(ants_req).values_list("id", flat=True))
        self.assertIn(chennai.id, bcww_ids)
        self.assertIn(kolkata.id, bcww_ids)
        self.assertEqual(ants_ids, set())

        page = unified_leads_page(bcww_req, page=1, limit=50)
        page_ids = {row["id"] for row in page}
        self.assertIn(f"landing-{chennai.id}", page_ids)
        self.assertIn(f"landing-{kolkata.id}", page_ids)
        chennai_row = next(row for row in page if row["id"] == f"landing-{chennai.id}")
        self.assertEqual(chennai_row["mobile"], "")
        self.assertEqual(chennai_row["email"], "")

        detail = unified_lead_detail(f"landing-{chennai.id}", include_detail=True, request=bcww_req)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["mobile"], "")
        self.assertIsNone(
            unified_lead_detail(f"landing-{chennai.id}", include_detail=True, request=ants_req)
        )

    def test_bcww_report_keeps_lead_type_filter(self):
        bcww, _ = self._users()
        landing = self._landing()
        campaign = CrmLead.objects.create(
            full_name="Meta Campaign Lead",
            mobile="9000000199",
            email="meta.campaign@example.com",
            state="Tamil Nadu",
            city="Chennai",
            source=CrmLeadSource.JULY_META,
        )

        def _report(agency_lead=""):
            path = "/crm/leads/reports"
            if agency_lead:
                path += f"?agencyLead={agency_lead}"
            req = RequestFactory().get(path)
            req.user = bcww
            return agency_lead_report_data(req)

        all_rows = _report()["leads"]
        all_ids = {row["id"] for row in all_rows}
        self.assertIn(campaign.id, all_ids)
        self.assertIn(f"landing-{landing.id}", all_ids)
        landing_row = next(row for row in all_rows if row["id"] == f"landing-{landing.id}")
        campaign_row = next(row for row in all_rows if row["id"] == campaign.id)
        self.assertEqual(landing_row["lead_type"], "Admission")
        self.assertEqual(campaign_row["lead_type"], "Campaign")

        campaign_ids = {row["id"] for row in _report("campaign")["leads"]}
        self.assertIn(campaign.id, campaign_ids)
        self.assertNotIn(f"landing-{landing.id}", campaign_ids)

        landing_ids = {row["id"] for row in _report("landing")["leads"]}
        self.assertIn(f"landing-{landing.id}", landing_ids)
        self.assertNotIn(campaign.id, landing_ids)


class LandingSheetAutoAssignTests(TestCase):
    """2G city LPs auto-assign to the admission mapping-sheet logins."""

    def setUp(self):
        from accounts.management.commands.seed_crm_team_users import (
            KERALA_ALL,
            KERALA_SOUTH,
        )
        from accounts.models import UserRole

        def _user(email, name, states, cities="", designation="Manager"):
            return User.objects.create_user(
                email=email,
                password="testpass123",
                role=UserRole.CRM,
                full_name=name,
                crm_designation=designation,
                crm_states=states,
                crm_cities=cities,
            )

        self.jayaraj = _user(
            "jayaraj@timekidspreschools.com", "M. Jayaraj", "Tamil Nadu"
        )
        self.sivaraman = _user(
            "sivaraman@timekidspreschools.com",
            "Sivaraman",
            "Tamil Nadu",
            designation="Assistant Manager",
        )
        self.satish = _user(
            "satishmenon@timekidspreschools.com",
            "Satish Menon",
            "Kerala",
            KERALA_SOUTH,
        )
        self.vivek = _user(
            "vivek@timekidspreschools.com", "Vivek RT", "Kerala", KERALA_ALL
        )
        self.anoop = _user(
            "anoopkunjan@timekidspreschools.com",
            "Anoop Kunjan",
            "Kerala",
            designation="Assistant Manager",
        )
        self.sujee = _user(
            "sujee@timekidspreschools.com",
            "Sujee",
            "Karnataka",
            designation="Regional Manager",
        )
        self.thimmesh = _user(
            "thimmesh.k@timekidspreschools.com", "Thimmesh", "Karnataka"
        )
        self.sai = _user(
            "saikishore@timekidspreschools.com",
            "Sai Kishore",
            "Andhra Pradesh, Telangana",
            designation="Dy Manager",
        )
        self.harshit = _user(
            "harshit@timekidspreschools.com",
            "Harshit Katare",
            "Andhra Pradesh, Telangana",
            designation="Assistant Manager",
        )
        self.deepak = _user(
            "deepaknikam@timekidspreschools.com",
            "Deepak Nikam",
            "Maharashtra",
            designation="Assistant Manager",
        )
        self.jyoti = _user(
            "jyoti.mishra@timekidspreschools.com",
            "Jyoti Mishra",
            "Bihar, Chhattisgarh, Odisha, West Bengal",
            "Patna,Bhubaneswar,Kolkata,Howrah",
            designation="Zonal Manager",
        )

    def _submit(self, city, n):
        from enquiries.landing_submit import handle_landing_enquiry_post

        phone = f"9000001{n:03d}"
        return handle_landing_enquiry_post(
            {
                "name": f"Parent {city}",
                "telephone": phone,
                "email": f"lp.{city.lower().replace(' ', '')}{n}@example.com",
                "city": city,
                "Location": f"{city} Centre",
                "source": "Google",
            }
        )

    @patch("enquiries.emails.send_landing_enquiry_emails", return_value=None)
    @patch("enquiries.emails.send_crm_heads_new_lead_reminder", return_value=True)
    def test_2g_cities_go_to_sheet_logins(self, _heads, _landing_mail):
        expected = {
            "Chennai": "jayaraj@timekidspreschools.com",
            "Coimbatore": "jayaraj@timekidspreschools.com",
            "Ernakulam": "satishmenon@timekidspreschools.com",
            "Trivandrum": "satishmenon@timekidspreschools.com",
            "Palakkad": "vivek@timekidspreschools.com",
            "Thrissur": "vivek@timekidspreschools.com",
            "Bangalore": "sujee@timekidspreschools.com",
            "Pune": "deepaknikam@timekidspreschools.com",
            "Kolkata": "jyoti.mishra@timekidspreschools.com",
        }
        for i, (city, email) in enumerate(expected.items(), start=1):
            self._submit(city, i)
            row = KidsEnquiry.objects.get(city=city)
            self.assertEqual(row.state, {
                "Chennai": "Tamil Nadu",
                "Coimbatore": "Tamil Nadu",
                "Ernakulam": "Kerala",
                "Trivandrum": "Kerala",
                "Palakkad": "Kerala",
                "Thrissur": "Kerala",
                "Bangalore": "Karnataka",
                "Pune": "Maharashtra",
                "Kolkata": "West Bengal",
            }[city])
            self.assertIsNotNone(row.assigned_user_id, city)
            self.assertEqual(row.assigned_user.email.lower(), email, city)

        self._submit("Hyderabad", 99)
        hyd = KidsEnquiry.objects.get(city="Hyderabad")
        self.assertEqual(hyd.state, "Telangana")
        self.assertIn(
            hyd.assigned_user.email.lower(),
            {
                "saikishore@timekidspreschools.com",
                "harshit@timekidspreschools.com",
            },
        )


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


class AdmissionVsFranchiseLeadSplitTests(SimpleTestCase):
    def test_landing_google_source_is_admission_not_franchise(self):
        class KidsEnquiry:
            enquiry_type = "Admission Enquiry"
            landing_page_url = ""

        self.assertEqual(resolve_notify_lead_kind(KidsEnquiry(), "Landing (Google)"), "admission")

    def test_landing_google_label_without_row_is_admission(self):
        self.assertEqual(resolve_notify_lead_kind(None, "Landing (Google)"), "admission")

    def test_timekids_2g_crm_url_is_admission(self):
        class CrmLead:
            landing_page_url = "https://www.timekidspreschools.in/timekids-2g/landing-page.html?gclid=ABC"
            enquiry_type = ""

        self.assertEqual(resolve_notify_lead_kind(CrmLead(), "BCWW_Google"), "admission")


class AdmissionNotInFranchiseListTests(TestCase):
    def test_city_lp_and_website_admission_stay_out_of_franchise_filters(self):
        admin = User.objects.create_user(
            email="admin@timekids.com",
            password="testpass123",
            role="CRM",
            full_name="Admin",
            is_superuser=True,
        )
        landing = KidsEnquiry.objects.create(
            name="Admission LP",
            mobile="9000000991",
            mobileno="9000000991",
            email="lp.admit@example.com",
            state="Tamil Nadu",
            city="Chennai",
            location="Anna Nagar",
            enquiry_type="Admission Enquiry",
            source="Google",
        )
        Enquiry.objects.create(
            enquiry_type=EnquiryType.ADMISSION,
            name="Website Admit",
            email="web.admit@example.com",
            phone="9000000992",
            city="Chennai",
        )
        misfiled = CrmLead.objects.create(
            full_name="Misfiled City LP",
            mobile="9000000993",
            email="misfiled@example.com",
            state="Tamil Nadu",
            city="Chennai",
            source=CrmLeadSource.JULY_LP,
            landing_page_url="https://www.timekidspreschools.in/timekids-2g/landing-page.html?gclid=XYZ",
            gclid="XYZ",
        )
        franchise_lp = CrmLead.objects.create(
            full_name="Franchise Google LP",
            mobile="9000000994",
            email="franchise.lp@example.com",
            state="Tamil Nadu",
            city="Chennai",
            source=CrmLeadSource.JULY_LP,
            landing_page_url="https://www.timekidspreschools.in/Timekids-lp-TKKTAM/?gclid=FRAN",
            gclid="FRAN",
        )

        factory = RequestFactory()
        franchise_req = factory.get("/enquiries/admin/crm-leads/", {"source": "franchise_all"})
        franchise_req.user = admin
        google_req = factory.get("/enquiries/admin/crm-leads/", {"source": "google"})
        google_req.user = admin
        landing_req = factory.get("/enquiries/admin/crm-leads/", {"source": "landing"})
        landing_req.user = admin

        franchise_ids = {row["id"] for row in unified_leads_page(franchise_req, page=1, limit=50)}
        google_ids = {row["id"] for row in unified_leads_page(google_req, page=1, limit=50)}
        landing_ids = {row["id"] for row in unified_leads_page(landing_req, page=1, limit=50)}

        self.assertNotIn(f"landing-{landing.id}", franchise_ids)
        self.assertNotIn(f"enquiry-{Enquiry.objects.get(email='web.admit@example.com').id}", franchise_ids)
        self.assertNotIn(f"crm-{misfiled.id}", franchise_ids)
        self.assertIn(f"crm-{franchise_lp.id}", franchise_ids)

        self.assertNotIn(f"crm-{misfiled.id}", google_ids)
        self.assertIn(f"crm-{franchise_lp.id}", google_ids)

        self.assertIn(f"landing-{landing.id}", landing_ids)
        self.assertIn(f"crm-{misfiled.id}", landing_ids)
        self.assertNotIn(f"crm-{franchise_lp.id}", landing_ids)

        self.assertEqual(_filter_crm_qs(franchise_req).filter(pk=misfiled.id).count(), 0)
        self.assertEqual(_filter_crm_qs(landing_req, admission_city_lp_only=True).filter(pk=misfiled.id).count(), 1)

