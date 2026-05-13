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
    return out


DEFAULT_HOME_PAGE_DATA: dict = {
    "key_navigation": [
        {"icon": "/icon-tour.png", "alt": "Virtual Tour", "href": "/gallery", "label": "Virtual\nTour", "nav_class": "nav-link1"},
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
        "title_prefix": "Franchise",
        "title_accent": "Opportunity",
        "subtitle": "Partner with India's trusted preschool brand and build a rewarding business",
    },
    "benefits": [
        {
            "icon": "Award",
            "title": "Strong Brand Name",
            "description": "Leverage 17 years of T.I.M.E. Kids legacy and 30+ years of T.I.M.E. Group expertise",
        },
        {
            "icon": "DollarSign",
            "title": "Low Investment, High Returns",
            "description": "Profitable business model with quick ROI and sustainable growth",
        },
        {
            "icon": "BookOpen",
            "title": "Complete Curriculum Support",
            "description": "NEP 2020 updated curriculum, teaching materials, and activity plans",
        },
        {
            "icon": "Users",
            "title": "Regular Staff Training",
            "description": "Continuous training programs for teachers and staff development",
        },
        {
            "icon": "Headphones",
            "title": "Operational Support",
            "description": "End-to-end support in setup, marketing, and daily operations",
        },
        {
            "icon": "TrendingUp",
            "title": "Marketing Assistance",
            "description": "National and local marketing support to grow your centre",
        },
    ],
    "offerings": [
        "Proven business model with 250+ successful centres",
        "Comprehensive training for franchisees and staff",
        "Marketing and promotional materials",
        "Technology platform for operations",
        "Quality assurance and monitoring",
        "Parent engagement programs",
    ],
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
            "ageGroup": "2 - 3 years",
            "duration": "2-3 hours",
            "description": "A magical start to learning! We focus on sensory play, making friends, and discovering the colorful world around us.",
            "features": ["Messy & Sensory Play", "Music & Dance", "Making Friends", "Fun with Colors"],
        },
        {
            "image": "/2 (1).png",
            "name": "Nursery",
            "ageGroup": "3 - 4 years",
            "duration": "3-4 hours",
            "description": "Building bridges to big ideas! Hands-on activities that spark curiosity, language, and creativity in little minds.",
            "features": ["Story Time Fun", "Arts & Crafts", "Counting Games", "Outdoor Exploration"],
        },
        {
            "image": "/2.png",
            "name": "Pre-Primary 1",
            "ageGroup": "4 - 5 years",
            "duration": "4 hours",
            "description": "Ready, set, grow! We introduce phonics, writing, and numbers through exciting themes and interactive play.",
            "features": ["Phonics & Reading", "Writing Fun", "Number Magic", "World Around Us"],
        },
        {
            "image": "/16.png",
            "name": "Pre-Primary 2",
            "ageGroup": "5 - 6 years",
            "duration": "4-5 hours",
            "description": "Future school superstars! Advanced concepts in math, science, and language to prep for big school with confidence.",
            "features": ["Little Scientists", "Math Whiz", "Creative Writing", "Public Speaking"],
        },
        {
            "image": "/day care.png",
            "name": "Day Care",
            "ageGroup": "2 - 10 years",
            "duration": "Full Day",
            "description": "A home away from home! Safe, loving, and engaging care with nutritious meals and help with homework.",
            "features": ["Homework Help", "Yummy Meals", "Nap Time", "Free Play"],
        },
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
