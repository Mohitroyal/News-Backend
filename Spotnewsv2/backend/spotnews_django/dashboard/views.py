from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required(login_url='/auth/login/')
def dashboard_view(request):
    return render(request, 'dashboard/dashboard.html')

@login_required(login_url='/auth/login/')
def profile_view(request):
    return render(request, 'dashboard/profile.html')

@login_required(login_url='/auth/login/')
def settings_view(request):
    return render(request, 'dashboard/settings.html')
