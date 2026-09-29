from django.urls import path
from tokens import views

urlpatterns = [
    path('', views.home),
    path('tokens/<uuid:token_id>/', views.detail_page),
    path('tokens/<uuid:token_id>/manage/', views.manage_page),
    path('api/tokens/', views.collection),
    path('api/tokens/<uuid:token_id>/', views.detail),
    path('api/tokens/<uuid:token_id>/qr.png', views.qr_file),
    path('api/tokens/<uuid:token_id>/workbook.xlsx', views.workbook_file),
]
