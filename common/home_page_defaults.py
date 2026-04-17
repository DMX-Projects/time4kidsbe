"""Default JSON for `HomePageContent` — mirrors current static homepage sections."""

DEFAULT_HOME_PAGE_DATA: dict = {
    "key_navigation": [
        {"icon": "/icon-tour.png", "alt": "Virtual Tour", "href": "/media", "label": "Virtual\nTour", "nav_class": "nav-link1"},
        {"icon": "/icon-gallery.png", "alt": "Photo / Video Gallery", "href": "/media", "label": "Photo / Video Gallery", "nav_class": "nav-link2"},
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
            {"image": "/infra.jpg", "title": "Safe Infrastructure", "desc": "Secure premises for complete peace of mind.", "color": "#FEE2E2", "accent": "#EF4444"},
            {"image": "/11.png", "title": "Trained Teachers", "desc": "Experienced educators nurturing your child.", "color": "#E0F2FE", "accent": "#0EA5E9"},
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
                "programName": "PP-1 & PP-2",
                "ageGroup": "4 - 6 years",
                "description": "Preparing for formal schooling with comprehensive education.",
                "color": "#6cc3d5",
                "yOffset": "-30px",
            },
            {
                "image": "/images/landing-banner.jpg",
                "programName": "Day Care",
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
