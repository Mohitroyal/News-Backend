"""Inspect generated demo artifacts; also keep summary notes within template widths."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from tokens.models import Token
from tokens.services import paths, field_row, atomic_save, lock
from openpyxl import load_workbook

token = Token.objects.get(token_number='KDP-DEMO-001')
workbook_path, qr = paths(token)
with lock():
    workbook = load_workbook(workbook_path)
    field_row(workbook['Token Summary'],'Token ID')[5].value = 'Demo copy; synthetic sample data.'
    field_row(workbook['Token Summary'],'Verification status')[5].value = 'Demo status; not real verification.'
    atomic_save(workbook,workbook_path)
    print({'token_id': str(token.id), 'sheets': workbook.sheetnames, 'qr_url':token.qr_url,
           'workbook':str(workbook_path), 'qr':str(qr)})
    workbook.close()
