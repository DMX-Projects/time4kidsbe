"""Default JSON for `HomePageContent` — mirrors current static homepage sections."""

import copy
import re

NEWS_TICKER_MAX_WORDS = 1000


def _count_words(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    return len(t.split())


def _truncate_to_word_limit(text: str, max_words: int = NEWS_TICKER_MAX_WORDS) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    words = t.split()
    if len(words) <= max_words:
        return t
    return " ".join(words[:max_words])


def _normalize_news_ticker_items(data: dict) -> None:
    """Enforce per-line word cap for home page Latest News & Updates ticker."""
    raw_items = data.get("news_ticker_items")
    if not isinstance(raw_items, list):
        return
    cleaned = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        text = _truncate_to_word_limit(str(row.get("text") or ""))
        if text:
            cleaned.append({"text": text})
    if cleaned:
        data["news_ticker_items"] = cleaned


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


def normalize_home_page_data(data):
    """Split legacy single-row PP-1+PP-2 into two programs (matches frontend merge)."""
    if not isinstance(data, dict):
        return data
    out = copy.deepcopy(data)
    pp = out.get("programs_preview")
    if not isinstance(pp, dict):
        return out
    programs = pp.get("programs")
    if not isinstance(programs, list):
        return out
    default_programs = DEFAULT_HOME_PAGE_DATA["programs_preview"]["programs"]
    pp1 = next((p for p in default_programs if p.get("programName") == "PP-1"), None)
    pp2 = next((p for p in default_programs if p.get("programName") == "PP-2"), None)
    if not pp1 or not pp2:
        return out
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
    _normalize_news_ticker_items(out)
    return out


VIRTUAL_TOUR_MAPS_URL = "https://www.google.com/maps/embed?pb=!1m0!3m2!1sen!2s!4v1456003231726!6m8!1m7!1sUEc7Ta_OzQcAAAQq3Rq0gw!2m2!1d17.40666583994208!2d78.48091207922675!3f90!4f0!5f0.4000000000000002"

DEFAULT_HOME_PAGE_DATA: dict = {
    "key_navigation": [
        {"icon": "/icon-nearstcenter.png", "alt": "Find your Nearest Centre", "href": "/locate-centre", "label": "Find your Nearest  Centre", "nav_class": "nav-link3"},
        {"icon": "/icon-franchise.png", "alt": "Become a Franchise", "href": "/franchise", "label": "Become a Franchise", "nav_class": "nav-link1"},
        {
            "icon": "/icon-tour.png",
            "alt": "Virtual Tour",
            "href": VIRTUAL_TOUR_MAPS_URL,
            "label": "Virtual\nTour",
            "nav_class": "nav-link1",
            "external": True,
        },
        {"icon": "/icon-gallery.png", "alt": "Photo / Video Gallery", "href": "/gallery", "label": "Photo / Video Gallery", "nav_class": "nav-link2"},
        {
            "icon": "/icon-brochure.png",
            "alt": "Download Brochure",
            "href": "https://www.timekidspreschools.in/uploads/pc/TIME-Kids-Franchise%20Brochure.pdf",
            "label": "Download Brochure",
            "nav_class": "nav-link2",
            "external": True,
        },
        {"icon": "/icon-media.svg", "alt": "Media", "href": "/gallery", "label": "Media", "nav_class": "nav-link3"},
    ],
    "franchise_benefits": [
        "Low Investment High Returns",
        "Strong Brand Name of T.I.M.E.",
        "Complete Curriculum Support",
        "Regular Staff Training",
        "Operational Support",
    ],
    "news_ticker_items": [
        {
            "text": "Our New centres opened for Academic year 2026-27 (Bengaluru – Dommasandra, Horamavu New, JP Nagar 9th Phase, Kamakshipalya) (Bhadrak – Motel Chhak) (Bhubaneswar – Patrapada) (Chennai – Chitlapakkam, Kovur, Mugalivakkam New, Porur, Pozhichalur, Tondiarpet New, West Mambalam) (Cuttack – CDA) (Ernakulam – Irumpanam) (Guntakal – Alur Road) (Guntur – Krishna Nagar) (Hyderabad – Ameenpur, Goshamahal, Kuntloor, Medchal, Presidency Avenue – Alwal, RR Colony – Ameenpur, Sri Ram Nagar - Jeedimetla) (Kolkata – Kestopur) (Kollam – Paravur) (Kozhikode – Pantheerankav) (Pathanamthitta – Changanassery) (Patna – Gola Road New, Khagaul Road, Priyadarshi) (Thrissur – Chiyyaram, Nellikunnu) (Tiruvannamalai – Arani) (Trichy – Pon Nagar) (Trivandrum – Kalathukal, Attingal, Vettu Road)",
        },
    ],
    "updates_empty_message": "Add scrolling news lines under Admin → Home page content → Latest news ticker.",
    "intro": {
        "title": "Welcome to T.I.M.E. Kids",
        "subtitle": "A chain of pre-schools launched by T.I.M.E., the national leader in entrance exam training.",
        "paragraphs": [
            "T.I.M.E. Kids pre-schools is a chain of pre-schools launched by T.I.M.E., the national leader in entrance exam training. After its hugely successful beginning in Hyderabad, T.I.M.E. Kids with 250+ pre-schools in 60 cities across India is now poised for major expansion across the country.",
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
            {"image": "/nep-2020-curriculum.png", "title": "NEP 2020 Curriculum", "desc": "Modern curriculum for holistic growth.", "color": "#FFEDD5", "accent": "#F97316"},
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
                "ageGroup": "Age group : 2-3 years",
                "description": "Introduction to social interaction and basic motor skills.",
                "color": "#ef5f5f",
                "yOffset": "-20px",
            },
            {
                "image": "/images/nursery_girl.png",
                "programName": "Nursery",
                "ageGroup": "Age group : 3-4 years",
                "description": "Building foundation for language, numbers, and expression.",
                "color": "#fbd267",
                "yOffset": "40px",
                "imageStyle": {"objectPosition": "center 20%"},
            },
            {
                "image": "/1.png",
                "programName": "PP-1",
                "ageGroup": "Age group : 4-5 years",
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
                "ageGroup": "Age group : 5-6 years",
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
                "ageGroup": "Age group : 2-10 years",
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


KIDS_TEACHER_RATIO_FAQ = {
    "question": "What is the Kids-teacher ratio?",
    "answer": "We maintain a low Kids-teacher ratio of 1:20 to ensure personalized attention for every child.",
}


def _is_kids_teacher_ratio_faq(question: str) -> bool:
    if not question:
        return False
    q = str(question)
    return bool(re.search(r"teacher\s*ratio", q, re.IGNORECASE)) and bool(
        re.search(r"(student|kids)", q, re.IGNORECASE)
    )


def normalize_admission_faq(faq: dict) -> dict:
    if not isinstance(faq, dict):
        return faq
    question = str(faq.get("question") or "")
    answer = str(faq.get("answer") or "")
    if _is_kids_teacher_ratio_faq(question):
        return copy.deepcopy(KIDS_TEACHER_RATIO_FAQ)
    if re.search(r"teacher\s*ratio", question, re.IGNORECASE) and re.search(r"1\s*:\s*10", answer):
        return copy.deepcopy(KIDS_TEACHER_RATIO_FAQ)
    return {"question": question, "answer": answer}


def normalize_admission_page_data(data):
    if not isinstance(data, dict):
        return data
    out = copy.deepcopy(data)
    faqs = out.get("faqs")
    if isinstance(faqs, list):
        out["faqs"] = [normalize_admission_faq(f) for f in faqs]
    return out


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
        copy.deepcopy(KIDS_TEACHER_RATIO_FAQ),
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
            "author": "T.I.M.E. Kids",
            "video_url": "https://iframe.mediadelivery.net/embed/117208/05fa5317-8993-4f3e-b24b-a9b7f61175ef?autoplay=true",
            "thumbnail_url": "/feature-annual-day-celebrations.png",
        },
        {
            "title": "School Activities",
            "author": "T.I.M.E. Kids",
            "video_url": "https://iframe.mediadelivery.net/embed/117208/76ca3eeb-db55-4472-8a3d-dd9bc1ac7f62?autoplay=true",
            "thumbnail_url": "/feature-safe-infrastructure.png",
        },
        {
            "title": "Happy Moments",
            "author": "Parents Testimonials",
            "video_url": "https://iframe.mediadelivery.net/embed/117208/61fb5949-de73-42f7-8c27-f4918ff9b9ff?autoplay=true",
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
        {
            "title": "What our Franchise has to say about T.I.M.E. Kids",
            "author": "T.I.M.E. Kids",
            "location": "",
            "video_url": "",
            "thumbnail_url": "/feature-annual-day-celebrations.png",
        },
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
            "ageGroup": "Age group : 2-3 years",
            "duration": "2-3 hours",
            "description": PROGRAM_DESCRIPTIONS["play_group"],
            "features": ["Smooth Transition Beyond Home", "Sensory & Guided Play", "Music and Storytelling", "Social and Motor Skills"],
        },
        {
            "image": "/2 (1).png",
            "name": "Nursery",
            "ageGroup": "Age group : 3-4 years",
            "duration": "3-4 hours",
            "description": PROGRAM_DESCRIPTIONS["nursery"],
            "features": ["Language and Phonics", "Numbers and Pre-Writing", "Creative Expression", "Confidence and Independence"],
        },
        {
            "image": "/2.png",
            "name": "PP-1 / Junior KG / LKG",
            "ageGroup": "Age group : 4-5 years",
            "duration": "4-5 hours",
            "description": PROGRAM_DESCRIPTIONS["pp1"],
            "features": ["Pre-Reading and Phonics", "Number Concepts", "Logical Thinking", "Projects and Role Play"],
        },
        {
            "image": "/16.png",
            "name": "PP-2 / Senior KG / UKG",
            "ageGroup": "Age group : 5-6 years",
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

# Global “Our Classes” card images on every centre page (/locations/...).
CENTRE_PROGRAM_CARDS_DATA: dict = {
    "cards": [
        {"id": 1, "image": "/1.png"},
        {"id": 2, "image": "/2 (1).png"},
        {"id": 3, "image": "/2.png"},
        {"id": 4, "image": "/16.png"},
        {"id": 5, "image": "/day care.png"},
    ],
}


FAQ_PAGE_DATA: dict = {
    "banner_images": ["/faq-banner-new-1.png", "/faq-banner-new-2.png"],
    "faqs": [
        {
            "question": "Why send your child to T.I.M.E. Kids?",
            "answer": [
                "Your child learns to make friends and important social skills like caring and sharing.",
                "Our pre-schools provide a learning-through-play environment.",
                "We help children start learning important life skills early.",
                "Children feel comfortable among peers of the same age group.",
            ],
        },
        {
            "question": "Do the children have an opportunity to be creative each day?",
            "answer": [
                "Children get ample opportunities for artistic expression.",
                "Activities include painting, clay modelling, role play, etc.",
            ],
        },
        {
            "question": "How does T.I.M.E. Kids pre-schools helps children acquire different skills?",
            "answer": [
                "Our curriculum involves a blend of structural learning and free play.",
                "We focus on cognitive, physical, emotional, and social development through activities like puzzles, storytelling, group games, and interactive learning sessions.",
            ],
        },
        {
            "question": "Isn't it too early for a child of one-and-a-half year to be attending play school?",
            "answer": [
                "The first six years are critical for a child's brain development.",
                "Our program for this age group acts as a bridge between home and school, providing a secure and stimulating environment that encourages exploration and social interaction.",
            ],
        },
        {
            "question": "Are basic maths, language and science concepts included in each day's program?",
            "answer": [
                "Yes, we introduce fundamental concepts of numeracy, language, and environmental science through age-appropriate, play-based activities that make learning fun and engaging.",
            ],
        },
        {
            "question": "What is the importance of experienced educationists?",
            "answer": [
                "Experienced educationists ensure that the curriculum is developmentally appropriate, safe, and effective.",
                "They understand child psychology and can tailor learning experiences to meet the unique needs of every child.",
            ],
        },
        {
            "question": "Are manners and etiquette also important as studies?",
            "answer": [
                "Absolutely. We believe in holistic development.",
                "Along with academics, we emphasize value education, teaching children essential social manners, table etiquette, and respect for others.",
            ],
        },
        {
            "question": "Are admissions to the programs open through out the year?",
            "answer": [
                "Yes, admissions are generally open throughout the year, subject to the availability of seats in the respective program.",
            ],
        },
        {
            "question": "What is the procedure for enrolment to T.I.M.E. Kids pre-schools?",
            "answer": [
                "Parents can visit the nearest T.I.M.E. Kids centre to collect the admission kit.",
                "The process involves filling out an application form and interacting with the centre head. You can also enquire online through our website.",
            ],
        },
        {
            "question": "Why should we enrol in T.I.M.E. Kids?",
            "answer": [
                "T.I.M.E. Kids offers a proven curriculum, safe infrastructure, and trained facilitators.",
                "We focus on the all-round development of your child in a nurturing environment, backed by the trusted T.I.M.E. brand.",
            ],
        },
        {
            "question": "Does T.I.M.E. Kids pre-schools offer transportation facilities?",
            "answer": [
                "Most of our centres offer safe and reliable transportation facilities with female attendants.",
                "Please check with your specific centre for route availability.",
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
                "text": "T.I.M.E. Kids pre-schools is a chain of pre-schools launched by T.I.M.E., the national leader in entrance exam training. After its hugely successful beginning in Hyderabad, T.I.M.E. Kids with 250+ pre-schools in 60 cities across India is now poised for major expansion across the country.",
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
