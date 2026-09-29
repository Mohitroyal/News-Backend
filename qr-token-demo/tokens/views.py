import json
import logging
from functools import wraps
from io import BytesIO
from zipfile import BadZipFile

from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from filelock import Timeout

from .models import Token
from . import services


def api_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (services.InputError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        except services.ConflictError as exc:
            return JsonResponse({'error': str(exc)}, status=409)
        except (OSError, Timeout, BadZipFile) as exc:
            logging.getLogger(__name__).warning('Demo storage unavailable: %s', exc)
            return JsonResponse({'error': 'File storage is unavailable. Close the workbook in Excel, then retry the same request.'}, status=503)
    return wrapped


def body(request):
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise services.InputError('Send a JSON object.')
    return data


def ready(token_id):
    return get_object_or_404(Token, pk=token_id, state='READY')


@ensure_csrf_cookie
def home(request):
    return render(request, 'index.html')


@ensure_csrf_cookie
@never_cache
@api_errors
def detail_page(request, token_id):
    report = services.read_token(ready(token_id))
    summary = report['summary']
    return render(request, 'report.html', {
        'report': report, 'project': summary.get('Project'),
        'facility': summary.get('Facility'),
        'verification': summary.get('Verification status'),
        'biochar': summary.get('Biochar output'),
        'removal': summary.get('Net token removal'),
        'request_path': request.path,
    })


@ensure_csrf_cookie
def manage_page(request, token_id):
    ready(token_id)
    return render(request, 'detail.html', {'token_id': str(token_id)})


@never_cache
@require_http_methods(['GET', 'POST'])
@api_errors
def collection(request):
    if request.method == 'GET':
        return JsonResponse({'tokens': [services.metadata(t) for t in
                             Token.objects.filter(state='READY').order_by('-created_at')[:100]]})
    token, replay = services.create_token(body(request))
    return JsonResponse(services.read_token(token), status=200 if replay else 201)


@never_cache
@require_http_methods(['GET', 'PATCH'])
@api_errors
def detail(request, token_id):
    token = ready(token_id)
    if request.method == 'PATCH':
        services.update_status(token, body(request).get('verification_status'))
    return JsonResponse(services.read_token(token))


@require_http_methods(['GET'])
@api_errors
def qr_file(request, token_id):
    token = ready(token_id)
    _, path = services.paths(token)
    return FileResponse(path.open('rb'), content_type='image/png', filename=f'{token.token_number}.png')


@never_cache
@require_http_methods(['GET'])
@api_errors
def workbook_file(request, token_id):
    token = ready(token_id)
    path, _ = services.paths(token)
    with services.lock():
        content = path.read_bytes()
    return FileResponse(BytesIO(content), as_attachment=True,
                        filename=f'{token.token_number}.xlsx')
