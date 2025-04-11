from django.contrib import admin
from django.urls import path
from prediction.views import wheat_health_map, predict_wheat_health

urlpatterns = [
    path('admin/', admin.site.urls),
    path('map/', wheat_health_map, name='wheat_health_map'),
    path('predict/', predict_wheat_health, name='predict_wheat_health'),
]