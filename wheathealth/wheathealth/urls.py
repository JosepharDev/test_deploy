from django.contrib import admin
from django.urls import path, include
from prediction.views import wheat_health_map, predict_wheat_health
# from prediction.views import get_point_indices #growth_stage_data
from prediction.views import  point_analysis_page, extract_indices_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('map/', wheat_health_map, name='wheat_health_map'),
    path('predict/', predict_wheat_health, name='predict_wheat_health'),
    # path('growth-stage-data/', get_growth_stage_data, name='growth_stage_data'),
    # path('growth_stage/', TemplateView.as_view(template_name='growth_stage.html'), name='growth_stage'),
    # path('get-point-indices/', get_point_indices, name='get_point_indices'),
    # path('extract_indices_view', extract_indices_view, name='extract_indices_view'),
    path('point-analysis-page/', point_analysis_page, name='point_analysis_page'),
    path('api/', include([
        path('indices/', extract_indices_view, name='get_indices'),])),
]