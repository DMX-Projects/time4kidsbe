"""Default JSON for `HomePageContent` — mirrors current static homepage sections."""

import copy
import re


def _is_legacy_combined_pp(program_name: str) -> bool:
    if not program_name or not str(program_name).strip():
        return False
    t = str(program_name).strip()
    one_line = " ".join(t.split()).lower()
    if one_line in ("pp-1 & pp-2", "pp1 & pp2"):
        return True
    if re.search(r"pp[-\u2013]?\s*1\s*([&+]|\band\b)\s*pp[-\u2013]?\s*2", one_line, re.IGNORECASE):
        return True
    lines = [x.strip() for x in re.split(r"\r?\n", t) if x.strip()]
    if len(lines) == 2:
        if re.match(r"^PP[-\u2013]?1$", lines[0], re.IGNORECASE) and re.match(
            r"^PP[-\u2013]?2$", lines[1], re.IGNORECASE
        ):
            return True
    return False


def _key_nav_href_key(href):
    """Lowercase path / URL key for dedupe (matches frontend `keyNavHrefKey`)."""
    if not href:
        return ""
    t = str(href).strip()
    if re.match(r"^https?://", t, re.I):
        try:
            from urllib.parse import urlparse, urlunparse

            u = urlparse(t)
            path = (u.path or "").rstrip("/") or "/"
            base = urlunparse((u.scheme.lower(), u.netloc.lower(), path, "", "", ""))
            return base.rstrip("/") if len(base) > 1 else base
        except Exception:
            return t.lower()
    p = t if t.startswith("/") else "/" + t
    lower = p.lower()
    if len(lower) > 1 and lower.endswith("/"):
        return lower[:-1]
    return lower


def _key_nav_slot(row):
    """One slot per quick-link tile so duplicates are dropped (matches frontend `keyNavSlot`)."""
    if not isinstance(row, dict):
        return "other:invalid"
    icon = (row.get("icon") or "").strip().lower()
    label = " ".join((row.get("label") or "").split()).lower()
    alt = (row.get("alt") or "").strip().lower()
    h = _key_nav_href_key(row.get("href") or "")

    if icon.endswith("icon-tour.png") or re.search(r"^virtual\s*tour\b", label, re.I) or "virtual tour" in alt:
        return "tour"
    if icon.endswith("icon-gallery.png") or re.search(r"photo\s*/\s*video\s*gallery", label, re.I) or re.search(
        r"photo.*video.*gallery", label, re.I
    ):
        return "gallery"
    if (
        "nearstcenter" in icon
        or "locate-centre" in h
        or re.search(r"find\s*your\s*nearest", label, re.I)
        or re.search(r"nearest\s*centre", label, re.I)
    ):
        return "locate"
    if "icon-franchise" in icon or h.endswith("/franchise") or re.search(r"become\s*a?\s*franchise", label, re.I):
        return "franchise"
    if "brochure" in icon or re.search(r"\.pdf(\b|[?#])", h, re.I) or re.search(r"download\s*brochure", label, re.I):
        return "brochure"
    if (
        icon.endswith("icon-media.svg")
        or "icon-television" in icon
        or "tv-commercial" in h
        or re.fullmatch(r"media", label, re.I)
        or re.search(r"tv\s*commercial", label, re.I)
    ):
        return "media"

    if h:
        return f"other:{h}"
    return f"other:icon:{icon or 'none'}:{label[:48]}"


def _dedupe_key_nav_by_slot(rows):
    seen = set()
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        s = _key_nav_slot(r)
        if s in seen:
            continue
        seen.add(s)
        out.append(r)
    return out


def normalize_key_navigation(rows, defaults):
    """Dedupe CMS rows by slot; append defaults only for missing slots."""
    if not isinstance(rows, list) or len(rows) == 0:
        return copy.deepcopy(defaults)
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append(
            {
                "icon": str(r.get("icon") or ""),
                "alt": str(r.get("alt") or ""),
                "href": str(r.get("href") or ""),
                "label": str(r.get("label") or ""),
                "nav_class": str(r.get("nav_class") or "nav-link1"),
                "external": bool(r.get("external")),
            }
        )
    merged = _dedupe_key_nav_by_slot(out)
    seen_slots = {_key_nav_slot(x) for x in merged}
    for d in defaults:
        slot = _key_nav_slot(d)
        if slot in seen_slots:
            continue
        merged.append(copy.deepcopy(d))
        seen_slots.add(slot)
    return _dedupe_key_nav_by_slot(merged)


def normalize_home_page_data(data):
    """Split legacy single-row PP-1+PP-2 into two programs; dedupe key navigation (matches frontend)."""
    if not isinstance(data, dict):
        return data
    out = copy.deepcopy(data)
    pp = out.get("programs_preview")
    if isinstance(pp, dict):
        programs = pp.get("programs")
        if isinstance(programs, list):
            default_programs = DEFAULT_HOME_PAGE_DATA["programs_preview"]["programs"]
            pp1 = next((p for p in default_programs if p.get("programName") == "PP-1"), None)
            pp2 = next((p for p in default_programs if p.get("programName") == "PP-2"), None)
            if pp1 and pp2:
                new_programs = []
                for p in programs:
                    if not isinstance(p, dict):
                        new_programs.append(p)
                        continue
                    name = (p.get("programName") or "").strip()
                    if _is_legacy_combined_pp(name):
                        new_programs.append(copy.deepcopy(pp1))
                        new_programs.append(copy.deepcopy(pp2))
                    else:
                        new_programs.append(p)
                pp["programs"] = new_programs
    kn = out.get("key_navigation")
    if kn is not None:
        out["key_navigation"] = normalize_key_navigation(kn, DEFAULT_HOME_PAGE_DATA["key_navigation"])
    return out


VIRTUAL_TOUR_MAPS_URL = "https://www.google.com/maps/embed?pb=!1m0!3m2!1sen!2s!4v1456003231726!6m8!1m7!1sUEc7Ta_OzQcAAAQq3Rq0gw!2m2!1d17.40666583994208!2d78.48091207922675!3f90!4f0!5f0.4000000000000002"

DEFAULT_HOME_PAGE_DATA: dict = {
    "key_navigation": [
        {
            "icon": "/icon-tour.png",
            "alt": "Virtual Tour",
            "href": VIRTUAL_TOUR_MAPS_URL,
            "label": "Virtual\nTour",
            "nav_class": "nav-link1",
            "external": True,
        },
        {"icon": "/icon-gallery.png", "alt": "Photo / Video Gallery", "href": "/gallery", "label": "Photo / Video Gallery", "nav_class": "nav-link2"},
        {"icon": "/icon-nearstcenter.png", "alt": "Find your Nearest Centre", "href": "/locate-centre", "label": "Find your Nearest  Centre", "nav_class": "nav-link3"},
        {"icon": "/icon-franchise.png", "alt": "Become a Franchise", "href": "/franchise", "label": "Become a Franchise", "nav_class": "nav-link1"},
        {
            "icon": "/icon-brochure.png",
            "alt": "Download Brochure",
            "href": "https://www.timekidspreschools.in/uploads/pc/TIME-Kids-Franchise%20Brochure.pdf",
            "label": "Download Brochure",
            "nav_class": "nav-link2",
            "external": True,
        },
        {"icon": "/icon-television.png", "alt": "TV Commercial", "href": "/tv-commercial", "label": "TV\nCommercial", "nav_class": "nav-link3"},
    ],
    "franchise_benefits": [
        "Low Investment High Returns",
        "Strong Brand Name of T.I.M.E.",
        "Complete Curriculum Support",
        "Regular Staff Training",
        "Operational Support",
    ],
    "franchise_advantage_videos": [
        {"poster": "/1.png", "src": "", "alt": "Franchise highlight 1"},
        {"poster": "/16.png", "src": "", "alt": "Franchise highlight 2"},
        {"poster": "/11.png", "src": "", "alt": "Franchise highlight 3"},
    ],
    "franchise_advantage_photos": [
        {"src": "/4.png", "alt": "Franchise photo 1"},
        {"src": "/17.png", "alt": "Franchise photo 2"},
        {"src": "/18.png", "alt": "Franchise photo 3"},
    ],
    "updates_empty_message": "New updates will appear here once they are added under Admin → Updates.",
    "intro": {
        "title": "Welcome to T.I.M.E. Kids",
        "subtitle": "A chain of pre-schools launched by T.I.M.E., the national leader in entrance exam training.",
        "paragraphs": [
            "T.I.M.E. Kids pre-schools is a chain of pre-schools launched by T.I.M.E., the national leader in entrance exam training. After its hugely successful beginning in Hyderabad, T.I.M.E. Kids with 350+ pre-schools is now poised for major expansion across the country.",
            "The programme at T.I.M.E. Kids pre-schools aims at making the transition from home to school easy, by providing the warm, safe and caring and learning environment that young children have at home. Our play schools offer wholesome, fun-filled and memorable childhood education to our children.",
            "We are backed by our educational expertise of over 27 years, well trained care providers and a balanced educational programme. The programme at T.I.M.E. Kids pre-schools is based on the principles of age-appropriate child development.",
        ],
    },
    "why_choose_us": {
        "heading_prefix": "Why Choose ",
        "heading_accent": "T.I.M.E. Kids?",
        "features": [
            {"image": "/feature-safe-infrastructure.png", "title": "Safe Infrastructure", "desc": "Secure premises for complete peace of mind.", "color": "#FEE2E2", "accent": "#EF4444"},
            {"image": "/feature-trained-teachers.png", "title": "Trained Teachers", "desc": "Experienced educators nurturing your child.", "color": "#E0F2FE", "accent": "#0EA5E9"},
            {"image": "/4.png", "title": "NEP 2020 Curriculum", "desc": "Modern curriculum for holistic growth.", "color": "#FFEDD5", "accent": "#F97316"},
            {"image": "/17.png", "title": "17 Years Legacy", "desc": "Educational expertise since 2005.", "color": "#DCFCE7", "accent": "#22C55E"},
            {"image": "/18.png", "title": "Caring Environment", "desc": "A second home for your little one.", "color": "#FDF2F8", "accent": "#EC4899"},
            {"image": "/12.png", "title": "Fun Learning", "desc": "Hands-on activities and play.", "color": "#F5F3FF", "accent": "#8B5CF6"},
        ],
    },
    "programs_preview": {
        "programs": [
            {
                "image": "/day care.png",
                "programName": "Play Group",
                "ageGroup": "2 - 3 years",
                "description": "Introduction to social interaction and basic motor skills.",
                "color": "#ef5f5f",
                "yOffset": "-20px",
            },
            {
                "image": "/images/nursery_girl.png",
                "programName": "Nursery",
                "ageGroup": "3 - 4 years",
                "description": "Building foundation for language, numbers, and expression.",
                "color": "#fbd267",
                "yOffset": "40px",
                "imageStyle": {"objectPosition": "center 20%"},
            },
            {
                "image": "/1.png",
                "programName": "PP-1",
                "ageGroup": "4 - 5 years",
                "description": (
                    "Expanding from school to the world around — curious, interactive, "
                    "and building strong foundations."
                ),
                "color": "#e74c3c",
                "yOffset": "-30px",
            },
            {
                "image": "/11.png",
                "programName": "PP-2",
                "ageGroup": "5 - 6 years",
                "description": (
                    "Confident learners ready for formal schooling — communication, "
                    "independence, and core skills."
                ),
                "color": "#2980b9",
                "yOffset": "20px",
            },
            {
                "image": "/images/landing-banner.jpg",
                "programName": "Summer Programs",
                "ageGroup": "2 - 10 years",
                "description": "Extended care with engaging activities throughout the day.",
                "color": "#ff9f43",
                "yOffset": "30px",
            },
        ],
    },
    "methodology": {
        "title": "Value based methodology",
        "items": [
            {"icon": "/methodology-icon1.png", "label": "Modular Furniture", "class": "nav-item1", "href": "/programs"},
            {"icon": "/methodology-icon2.png", "label": "Play-Learn methods", "class": "nav-item2", "href": "/programs"},
            {"icon": "/methodology-icon3.png", "label": "After School fun", "class": "nav-item3", "href": "/admission"},
            {"icon": "/methodology-icon4.png", "label": "Prioritizing Hygiene", "class": "nav-item4", "href": "/programs"},
            {"icon": "/methodology-icon5.png", "label": "Teaching Aids", "class": "nav-item5", "href": "/programs"},
            {"icon": "/methodology-icon6.png", "label": "Health Check-up", "class": "nav-item6", "href": "/programs"},
        ],
    },
}


ADMISSION_PAGE_DATA: dict = {
    "faq_section": {
        "title_prefix": "Got",
        "title_accent": "Questions?",
        "subtitle": "We have answers! Here is everything you need to know.",
        "image": "/2.png",
    },
    "why_preschool": [
        "Strong foundation for future",
        "Social & emotional growth",
        "Ready for big school!",
        "Brain development boost",
        "Confidence building",
    ],
    "why_time_kids": [
        "17 Years of Happiness",
        "250+ Centers in India",
        "NEP 2020 Compliant",
        "Loving & Trained Teachers",
        "Safe, Colorful Spaces",
        "Fun Activity Learning",
    ],
    "skills": [
        {"title": "Cognitive", "desc": "Problem solving", "icon": "Brain", "color": "bg-purple-500"},
        {"title": "Emotional", "desc": "Self-awareness", "icon": "Heart", "color": "bg-pink-500"},
        {"title": "Social", "desc": "Team work", "icon": "Users", "color": "bg-blue-500"},
        {"title": "Creative", "desc": "Art & Craft", "icon": "Palette", "color": "bg-orange-500"},
        {"title": "Musical", "desc": "Rhythm & Beat", "icon": "Music", "color": "bg-green-500"},
        {"title": "Physical", "desc": "Motor skills", "icon": "Dumbbell", "color": "bg-red-500"},
        {"title": "Language", "desc": "Reading skills", "icon": "BookOpen", "color": "bg-indigo-500"},
        {"title": "Nature", "desc": "Eco awareness", "icon": "Globe", "color": "bg-teal-500"},
    ],
    "faqs": [
        {
            "question": "What is the admission process?",
            "answer": "Fill out the enquiry form, schedule a school tour, meet with our counselor, complete the registration form, and submit required documents. We will guide you through each step.",
        },
        {
            "question": "What documents are required for admission?",
            "answer": "Birth certificate of the child, recent passport-size photographs, address proof, and parent ID proof. Additional documents may be required based on the program.",
        },
        {
            "question": "What is the fee structure?",
            "answer": "Fee structure varies by location and program. Please contact your nearest T.I.M.E. Kids centre or fill the enquiry form for detailed fee information.",
        },
        {
            "question": "Is there a trial class available?",
            "answer": "Yes, we offer trial classes so your child can experience our learning environment. Contact your nearest centre to schedule a trial class.",
        },
        {
            "question": "What is the student-teacher ratio?",
            "answer": "We maintain a low student-teacher ratio of 1:10 to ensure personalized attention for every child.",
        },
        {
            "question": "Are meals provided?",
            "answer": "Nutritious snacks and meals are provided for children enrolled in full-day programs and day care. We follow strict hygiene standards.",
        },
        {
            "question": "What safety measures are in place?",
            "answer": "We have CCTV surveillance, secure entry/exit points, trained staff, child-safe furniture and equipment, and regular safety drills.",
        },
        {
            "question": "Can parents visit the school?",
            "answer": "Yes, we encourage parents to schedule a visit. You can tour our facilities, meet our teachers, and understand our curriculum and approach.",
        },
    ],
    "happy_parents_videos": [
        {
            "title": "Annual Day Fun",
            "author": "T.I.M.E. Kids Kilpauk",
            "location": "Chennai",
            "video_url": "/chaninai kilpauk-AnnualDay-Video-2018-19.mp4",
            "thumbnail_url": "/feature-annual-day-celebrations.png",
        },
        {
            "title": "School Activities",
            "author": "T.I.M.E. Kids Chennai",
            "location": "Chennai",
            "video_url": "/chennai2.mp4",
            "thumbnail_url": "/feature-safe-infrastructure.png",
        },
        {
            "title": "Happy Moments",
            "author": "T.I.M.E. Kids Trichy",
            "location": "Trichy",
            "video_url": "/trichy-rajacolony.mp4",
            "thumbnail_url": "/5.jpeg",
        },
    ],
}


FRANCHISE_PAGE_DATA: dict = {
    "hero": {
        "title_prefix": "Why Partner with",
        "title_accent": "T.I.M.E. Kids Preschools?",
        "subtitle": "Join India's Most Trusted Preschool Franchise Network",
        "intro_paragraphs": [
            "Build a meaningful and rewarding business with T.I.M.E. Kids Preschools — a preschool brand backed by the educational legacy of T.I.M.E., one of India's most respected names in learning and test preparation.",
            "With decades of educational expertise, a strong nationwide presence, and a child-first philosophy, T.I.M.E. Kids offers aspiring entrepreneurs an opportunity to create both financial success and lasting social impact.",
        ],
    },
    "benefits_section": {
        "heading_prefix": "The T.I.M.E. Kids",
        "heading_accent": "Advantage",
        "blurb": "",
    },
    "benefits": [
        {
            "icon": "Award",
            "title": "Proven Educational Legacy",
            "description": (
                "Leverage the strength of a trusted education group that has built a growing network of 250+ preschool centres across 60+ cities, "
                "creating a strong foundation of trust, quality, and educational excellence."
            ),
        },
        {
            "icon": "TrendingUp",
            "title": "Fast-Growing Preschool Industry",
            "description": (
                "India's preschool sector continues to witness rapid growth, making this the ideal time to invest in early childhood education — "
                "a segment driven by increasing awareness of quality foundational learning among parents."
            ),
        },
        {
            "icon": "BookOpen",
            "title": "Research-Based Curriculum",
            "description": (
                "Gain access to a professionally designed and continuously evolving curriculum aligned with modern early learning methodologies "
                "and compatible with CBSE, ICSE, and SSC educational frameworks.\n\n"
                "The curriculum follows a playway method of teaching focused on the holistic development of every child, "
                "preparing them confidently for primary schooling."
            ),
        },
        {
            "icon": "Heart",
            "title": "Strong Brand Credibility",
            "description": (
                "Benefit from the reputation and trust associated with the T.I.M.E. brand — known nationwide for academic excellence, "
                "structured systems, and student success."
            ),
        },
        {
            "icon": "Headphones",
            "title": "Comprehensive Franchise Support",
            "description": (
                "At T.I.M.E. Kids, franchisees receive end-to-end support at every stage — from setup and launch to operations and long-term growth."
            ),
        },
    ],
    "offerings_section": {
        "heading_prefix": "Comprehensive",
        "heading_accent": "Franchise Support",
        "intro": (
            "At T.I.M.E. Kids, franchisees receive end-to-end support at every stage — from setup and launch to operations and long-term growth."
        ),
        "blurb": "",
    },
    "offerings": [
        "Infrastructure & Setup Guidance — Expert assistance in planning and establishing child-friendly infrastructure that meets preschool operational and safety standards.",
        "Recruitment & Teacher Training — Support in recruiting qualified staff along with professional training programs for teachers and centre teams.",
        "Marketing & Admissions Support — Guidance on local marketing initiatives, branding activities, parent outreach, and admissions strategies to help build strong enrolments.",
        "Academic & Operational Training — Comprehensive training on curriculum delivery, classroom management, child engagement practices, and day-to-day centre operations.",
        "Continuous Handholding — Ongoing academic and operational support designed to help centres achieve stability, sustained growth, and long-term profitability.",
    ],
    "getting_started": {
        "heading": "What You Need to Get Started",
        "intro": "We are looking for passionate individuals who believe in nurturing young learners while building a successful and impactful business.",
        "items": [
            {
                "title": "Space Requirement",
                "description": (
                    "Minimum 1,800 sq. ft. constructed area. Independent building or house in a good residential locality preferred."
                ),
            },
            {
                "title": "Investment",
                "description": (
                    "Approximate investment: ₹12–15 lakhs. Includes infrastructure setup and operational readiness for launching the preschool."
                ),
            },
        ],
    },
    "closing": {
        "heading": "Start Your Journey with T.I.M.E. Kids",
        "paragraphs": [
            "Become part of a growing national preschool network committed to creating safe, engaging, and joyful learning environments for children across India.",
            'Together, we can build centres that truly become a "second home" for every child.',
        ],
    },
    "quick_highlights": {
        "heading": "Quick Highlights",
        "items": [
            "250+ Centres Across India",
            "34+ Years of Educational Excellence",
            "Child-Safe & Non-Toxic Infrastructure Standards",
            "Low Investment with Strong Growth Potential",
            "High Social-Impact Business Opportunity",
            "End-to-End Academic & Operational Support",
            "Proven Systems & Structured Processes",
            "Trusted Brand with Nationwide Recognition",
        ],
    },
    "testimonials": [
        {"title": "Best business decision", "author": "Franchise Partner", "location": "Bangalore", "video_url": "", "thumbnail_url": ""},
        {"title": "Complete support from day one", "author": "Franchise Partner", "location": "Chennai", "video_url": "", "thumbnail_url": ""},
        {"title": "Rewarding and fulfilling", "author": "Franchise Partner", "location": "Pune", "video_url": "", "thumbnail_url": ""},
    ],
    "main_branch": {
        "heading_prefix": "Visit Our",
        "heading_accent": "Main Branch",
        "subtitle": "Come meet our team and explore our flagship centre",
        "map_embed_url": "https://www.google.com/maps/embed/v1/place?key=AIzaSyBFw0Qbyq9zTFTd-tUY6dZWTgaQzuU17R8&q=Siddamsetty+Complex+Parklane+Secunderabad+500003&zoom=15",
        "office_title": "T.I.M.E. Kids Corporate Office",
        "address_html": "Triumphant Institute of Management Education Pvt. (T.I.M.E.)<br />95B, Second Floor<br />Siddamsetty Complex<br />Parklane, Secunderabad<br />500003",
        "phone": "040-40088300",
        "fax": "040-27847334",
        "email": "info@timekidspreschools.com",
        "franchise_email": "franchise@timekidspreschools.com",
        "cell": "8096355335",
        "directions_url": "https://www.google.com/maps/dir/?api=1&destination=Siddamsetty+Complex+Secunderabad+500003",
        "directions_label": "Get Directions",
    },
    "brochure": {
        "heading": "Download Franchise Brochure",
        "subtitle": "Get detailed information about investment, support, and franchise benefits",
        "button_label": "Download Brochure (PDF)",
        "fallback_url": "https://www.timekidspreschools.in/uploads/pc/TIME-Kids-Franchise%20Brochure.pdf",
        "marketing_asset_slug": "franchise-brochure",
    },
}


PROGRAM_DESCRIPTIONS: dict = {
    "play_group": (
        "At TimeKids Play Group, we provide a warm, safe, and joyful environment where toddlers begin their learning journey through play, exploration, and interaction. "
        "The Play Group program is a child's first step into a world beyond home, focusing on a smooth transition through a caring and playful atmosphere. "
        "Our educators nurture a love for discovery, helping children understand the world around them while strengthening their cognitive and social abilities.\n\n"
        "The program focuses on developing social skills, sensory experiences, communication, and motor coordination through fun-filled activities, music, storytelling, and guided play. "
        "Our caring educators ensure that every child feels comfortable, confident, and emotionally secure while gradually adapting to a structured learning environment. "
        "We encourage curiosity, creativity, and independent expression, helping children build a strong foundation for future learning in a happy and nurturing atmosphere. "
        "It truly becomes a home away from home for your child."
    ),
    "nursery": (
        "The Nursery program at TimeKids is designed to nurture curiosity, confidence, and early learning skills in young minds. "
        "At this stage, the focus shifts toward building a strong foundation in language, numbers, and self-expression. "
        "Through activity-based learning, children are introduced to language development, phonics, numbers, creative expression, and social interaction in an engaging and enjoyable manner.\n\n"
        "Our curriculum encourages children to explore, ask questions, and develop communication and thinking abilities through stories, music, art, games, and hands-on activities. "
        "Children are also introduced to pre-writing strokes of alphabets and numbers. "
        "Special emphasis is placed on emotional development, classroom participation, and building independence, helping children smoothly transition into structured academic learning with confidence and enthusiasm."
    ),
    "pp1": (
        "The PP-1 program focuses on strengthening foundational academic and life skills through an interactive and child-friendly approach. "
        "Children are introduced to pre-reading, pre-writing, phonics, number concepts, logical thinking, and problem-solving activities that prepare them for advanced learning.\n\n"
        "The curriculum promotes creativity, confidence, communication, and teamwork through experiential learning, role play, projects, and classroom activities. "
        "The PP-1 program is designed to expand a child's horizons from the classroom to the world around them. "
        "We nurture curious and interactive learners by encouraging them to ask questions and explore how and why.\n\n"
        "The curriculum also focuses on building strong foundations in reading readiness, logical thinking, and environmental awareness. "
        "Our educators create a stimulating environment where every child is encouraged to explore their potential, develop independent thinking, and build the confidence required for formal schooling and lifelong learning."
    ),
    "pp2": (
        "The PP-2 program prepares children for a smooth transition into primary school by building strong academic readiness and essential life skills. "
        "The curriculum focuses on reading readiness, writing skill development, vocabulary building, mathematical concepts, reasoning, creativity, and independent learning.\n\n"
        "As the final preschool stage, the PP-2 program focuses on refining communication, independence, and core academic skills. "
        "Through engaging classroom activities, collaborative learning, and hands-on experiences, children develop confidence, communication abilities, and problem-solving skills.\n\n"
        "Equal importance is given to personality development, discipline, social interaction, and emotional growth, ensuring that children are well-prepared to confidently step into formal schooling with enthusiasm and a love for learning. "
        "Our graduates emerge as well-rounded individuals, equipped with the knowledge and social maturity needed to excel in any formal school environment."
    ),
    "summer": (
        "At TimeKids, we offer two types of Summer Programs: Summer Camp and Refresher Course.\n\n"
        "Summer Camp provides a safe, caring, and stimulating environment where children feel secure, happy, and engaged throughout the program. "
        "It combines supervised care with age-appropriate learning activities, creative play, storytelling, music, indoor games, and social interaction to ensure holistic development.\n\n"
        "With trained caregivers, child-friendly infrastructure, and a nurturing atmosphere, we focus on every child's emotional well-being, hygiene, comfort, and daily routine. "
        "The program is thoughtfully designed to support working parents while ensuring children enjoy a balanced day filled with learning, care, fun, and meaningful engagement.\n\n"
        "The camp includes a healthy mix of rest, nutritious meals, and supervised play. "
        "We also offer enrichment activities such as creative hobbies, physical games, and interactive group activities to keep children active, productive, and happy. "
        "Whether exploring a new storybook or participating in team activities, children receive personalized attention that supports their emotional and social development until they are reunited with their parents.\n\n"
        "The TimeKids Refresher Program focuses on improving writing readiness and confidence in young learners. "
        "Designed for children in the 3-4 years and 4-5 years age groups, the program includes pre-writing skills, writing improvement exercises, and activities that help children gain confidence in writing alphabets and numbers.\n\n"
        "The program prepares children for a smooth and confident transition into PP-1 and PP-2 after the summer break. "
        "As the name suggests, the Refresher Program strengthens and refreshes the basics of writing skills, making children more confident, fluent, and comfortable with writing activities appropriate to their age group."
    ),
}


PROGRAMS_PAGE_DATA: dict = {
    "hero": {
        "badge": "Bright futures start here",
        "title_prefix": "Our",
        "title_accent": "Programs",
        "subtitle": "Curiosity-led learning adventures for every stage of your child's magical early years.",
        "cta_label": "Enroll Your Child",
        "cta_href": "/admission",
    },
    "programs": [
        {
            "image": "/1.png",
            "name": "Play Group",
            "ageGroup": "Age Group: 2-3 Years",
            "duration": "2-3 hours",
            "description": PROGRAM_DESCRIPTIONS["play_group"],
            "features": ["Smooth Transition Beyond Home", "Sensory & Guided Play", "Music and Storytelling", "Social and Motor Skills"],
        },
        {
            "image": "/2 (1).png",
            "name": "Nursery",
            "ageGroup": "Age Group: 3-4 Years",
            "duration": "3-4 hours",
            "description": PROGRAM_DESCRIPTIONS["nursery"],
            "features": ["Language and Phonics", "Numbers and Pre-Writing", "Creative Expression", "Confidence and Independence"],
        },
        {
            "image": "/2.png",
            "name": "PP-1 / Junior KG / LKG",
            "ageGroup": "Age Group: 4-5 Years",
            "duration": "4 hours",
            "description": PROGRAM_DESCRIPTIONS["pp1"],
            "features": ["Pre-Reading and Phonics", "Number Concepts", "Logical Thinking", "Projects and Role Play"],
        },
        {
            "image": "/16.png",
            "name": "PP-2 / Senior KG / UKG",
            "ageGroup": "Age Group: 5-6 Years",
            "duration": "4-5 hours",
            "description": PROGRAM_DESCRIPTIONS["pp2"],
            "features": ["Reading and Writing Readiness", "Vocabulary and Maths", "Reasoning and Creativity", "Primary School Confidence"],
        },
        {
            "image": "/day care.png",
            "name": "Summer Programs",
            "ageGroup": "Summer Camp and Refresher Course",
            "duration": "Full Day",
            "description": PROGRAM_DESCRIPTIONS["summer"],
            "features": ["Summer Camp", "Refresher Course", "Writing Readiness", "Care, Play, and Enrichment"],
        },
    ],
}


FAQ_PAGE_DATA: dict = {
    "banner_images": ["/faq-banner-new-1.png", "/faq-banner-new-2.png"],
    "faqs": [
        {
            "question": "Why send your child to T.I.M.E. Kids ?",
            "answer": [
                "Your child learns to make friends, learns the important social skills of caring, sharing etc.",
                "Our pre-schools' provide an environment of learning through play.",
                "Our pre-schools are the best place for your child to start learning the important skills in life.",
                "Your child will feel comfortable in the presence of other children of the same age group.",
            ],
        },
        {
            "question": "Do the children have an opportunity to be creative each day?",
            "answer": [
                "Your child gets ample opportunity for his/her artistic expression at T.I.M.E. Kids pre-schools.",
                "Children are involved in various activities throughout the day for e.g.: painting, claymodelling, role play, etc.",
            ],
        },
        {
            "question": "How does T.I.M.E. Kids pre-schools helps children acquire different skills?",
            "answer": [
                "At T.I.M.E. Kids pre-schools, we plan and provide child centered fun-filled activities according to the different levels of development, interest and need. They are planned and sequenced in ways to foster children's motor, cognitive, language and socio-emotional development. At our pre-schools there is a balance in the daily schedule of small and large activities, group as well as individual activities, indoor and outdoor activities, physical and mental activities. Children soon learn to accept and respond to instructions given by the teachers.",
            ],
        },
        {
            "question": "Isn't it too early for a child of one-and-a-half year to be attending play school?",
            "answer": [
                "Studies have proved that the first six years of an individual's life are critical since development/growth takes place at its most rapid during in this period. Our Play schools provides the necessary environment for the overall development of the child. Children get the opportunity to pick up good language, for self expression, experimentation and problem solving.",
            ],
        },
        {
            "question": "Are basic maths, language and science concepts included in each day's program?",
            "answer": [
                "To understand better the world around them, Children's need to know maths and science concepts. They imbibe these at Play schools through activities and play.",
            ],
        },
        {
            "question": "What is the importance of experienced educationists?",
            "answer": [
                "Experienced educationists are essential because they understand the needs of every age group and are highly competent in their area of work.Teachers act mainly as facilitators and help children learn and apply concepts, Also they have a hands-on approach to teaching abstract concepts, solving problems and counselling children.",
            ],
        },
        {
            "question": "Are manners and etiquette also important as studies?",
            "answer": [
                "Etiquette and manners are important in today's world. They are developed in children as part of the curriculum at Play Schools.",
            ],
        },
        {
            "question": "Are admissions to the programs open through out the year?",
            "answer": [
                "Admissions are open through out the year (space permitting) but we recommend that children be enrolled at the start of the academic session (June) or at the start of the 2nd term (October)",
            ],
        },
        {
            "question": "What is the procedure for enrolment to T.I.M.E. Kids pre-schools?",
            "answer": [
                "Parents are welcome at any pre-school centers. We have an online form which can be downloaded and filled in. We require a copy of proof of date of birth, marks transcript (if the child has attended any school) and 2 recent passport size photographs of the child.",
            ],
        },
        {
            "question": "Why should we enrol in T.I.M.E. Kids ?",
            "answer": [
                "We provide:",
                "1.Exceptional Infrastructure",
                "2.Dedicated Faculty",
                "3.Safe, Secure and Clean environment",
                "4.Activity based curriculum",
                "5.Creative Teaching Philosophy",
                "6.Parent Involvement",
            ],
        },
        {
            "question": "Does T.I.M.E. Kids pre-schools offer transportation facilities?",
            "answer": [
                "Transport facilities are center specific and details can be had from the centre head at the time of admission.",
            ],
        },
        {
            "question": "I have a transferable job, Can I get my child transferred to another T.I.M.E. Kids pre-school?",
            "answer": [
                "Your child can be transferred to any of our centers for a nominal transfer fee.",
            ],
        },
        {
            "question": "Where can I find information on the fee structure?",
            "answer": [
                "Tuition fee is specific to each center. The Center head at our play school will provide all the information at the time of enrolment.",
            ],
        },
        {
            "question": "What are the programs that T.I.M.E. Kids pre-schools offers?",
            "answer": [
                "Our programs include:",
                "1. Playgroup - 1.5-2.5 years",
                "2. Nursery - 2.5-3.5 years",
                "3. Pre Primary-1 - 3.5-4.5 years",
                "4. Pre Primary-2 - 4.5-5.5 years",
            ],
        },
    ],
}


ABOUT_PAGE_DATA: dict = {
    "hero": {
        "badge_prefix": "Trusted by",
        "badge_suffix": "Schools Nationwide",
        "title_prefix": "About",
        "title_accent": "T.I.M.E. Kids",
        "tagline": "Where little dreamers become big achievers!",
        "subtitle": "A legacy of educational excellence spanning over 17 years in early childhood education",
    },
    "magical_story": {
        "title_prefix": "Our",
        "title_accent": "Magical",
        "title_suffix": "Story",
        "subtitle": "A journey of love, learning, and laughter!",
        "cards": [
            {
                "icon": "Building2",
                "icon_gradient": "from-orange-400 to-orange-600",
                "plane_position": "right",
                "text": "T.I.M.E. Kids pre-schools is a chain of pre-schools launched by T.I.M.E., the national leader in entrance exam training. After its hugely successful beginning in Hyderabad, T.I.M.E. Kids with 250+ pre-schools is now poised for major expansion across the country.",
            },
            {
                "icon": "Home",
                "icon_gradient": "from-pink-400 to-pink-600",
                "plane_position": "left",
                "text": "The programme at T.I.M.E. Kids pre-schools aims at making the transition from home to school easy, by providing the warm, safe and caring learning environment that young children have at home. Our play schools offer wholesome, fun-filled and memorable childhood education to our children.",
            },
            {
                "icon": "GraduationCap",
                "icon_gradient": "from-purple-400 to-purple-600",
                "plane_position": "right",
                "text": "T.I.M.E. Kids pre-schools are backed by our educational expertise of over 30 years, well trained care providers and a balanced educational programme. The programme at T.I.M.E. Kids pre-schools is based on the principles of age-appropriate child development practices.",
            },
        ],
    },
    "beliefs": {
        "heading_prefix": "What We",
        "heading_accent": "Believe In",
        "subtitle": "Our guiding stars in nurturing young minds",
        "vision": {
            "title": "Our Vision",
            "text": "To be the most trusted and preferred preschool chain in India, providing world-class early childhood education that nurtures every child's potential and prepares them for a bright future.",
        },
        "philosophy": {
            "title": "Our Philosophy",
            "text": "We believe in holistic development through play-based learning, fostering creativity, curiosity, and confidence in every child. Our approach combines traditional values with modern educational practices.",
        },
        "core_values_title": "Our Core Values",
        "core_values": [
            {
                "title": "Care & Safety",
                "text": "Every child is precious and deserves a nurturing environment",
                "icon": "Heart",
            },
            {
                "title": "Creativity First",
                "text": "Encouraging imagination and innovative thinking",
                "icon": "Sparkles",
            },
            {
                "title": "Holistic Growth",
                "text": "Developing mind, body, and character together",
                "icon": "BookOpen",
            },
        ],
    },
    "time_group": {
        "badge": "30+ Years of Excellence",
        "heading_prefix": "Part of the",
        "heading_accent": "T.I.M.E. Group",
        "subtitle": "Backed by three decades of educational excellence across multiple domains, bringing trusted expertise to early childhood education",
        "businesses": [
            {"name": "T.I.M.E.", "description": "National leader in entrance exam training", "icon": "Award"},
            {"name": "CLAT Training", "description": "Specialized coaching for law entrance exams", "icon": "Building2"},
            {"name": "School Level Programs", "description": "Academic support for school students", "icon": "Lightbulb"},
            {"name": "T.I.M.E. School", "description": "Complete K-12 education", "icon": "Target"},
        ],
        "trust_title_prefix": "Why Parents",
        "trust_title_accent": "Trust Us",
        "trust_items": [
            {"title": "Proven Track Record", "text": "30+ years of educational excellence and expertise", "icon": "Award"},
            {"title": "Trained Educators", "text": "Well-qualified and caring teachers who love children", "icon": "Users"},
            {"title": "Age-Appropriate Curriculum", "text": "Based on child development best practices", "icon": "BookOpen"},
            {"title": "Home-Like Environment", "text": "Safe, warm, and nurturing spaces for learning", "icon": "Home"},
        ],
    },
}
