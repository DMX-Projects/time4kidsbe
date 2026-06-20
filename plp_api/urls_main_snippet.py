from django.urls import include, path

urlpatterns = [
    # ... your existing urls ...
    path('api/plp/', include('plp_api.urls')),
]
