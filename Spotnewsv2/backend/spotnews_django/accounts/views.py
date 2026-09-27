from django.shortcuts import render, redirect

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    return render(request, 'accounts/login.html')

def verify_otp_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:dashboard')
    mobile = request.GET.get('mobile', '')
    return render(request, 'accounts/verify_otp.html', {'mobile': mobile})

def change_number_view(request):
    return redirect('accounts:login')
