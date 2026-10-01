from django.core.management.base import BaseCommand
from otp.services.msg91_service import MSG91Service

class Command(BaseCommand):
    help = 'Test MSG91 OTP Flow'

    def add_arguments(self, parser):
        parser.add_argument('mobile', type=str, help='Mobile number to test')

    def handle(self, *args, **kwargs):
        mobile = kwargs['mobile']
        normalized = ''.join(filter(str.isdigit, str(mobile)))
        if len(normalized) == 10:
            normalized = '91' + normalized
        
        self.stdout.write(self.style.SUCCESS("MSG91 TEST"))
        self.stdout.write("----------")
        resp = MSG91Service.send_otp(normalized, "123456")
        self.stdout.write(str(resp))
