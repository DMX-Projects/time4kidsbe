from django.urls import path

from . import views

urlpatterns = [
    path("", views.api_home, name="plp-api-home"),
    path("create-enrollment/", views.create_enrollment, name="plp-create-enrollment"),
    path("enroll/", views.create_enrollment, name="plp-enroll"),  # alias — same handler
    path("create-user/", views.create_plp_user, name="plp-create-user"),
    path("create-student-details/", views.create_student_details, name="plp-create-student-details"),
]
