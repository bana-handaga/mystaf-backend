from django.core.management.base import BaseCommand
from accounts.models import StafUser

class Command(BaseCommand):
    help = 'Setup data awal: buat superuser admin default'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin', help='Username admin')
        parser.add_argument('--password', default='Admin@1234', help='Password admin')
        parser.add_argument('--email', default='admin@mystaf.local', help='Email admin')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']

        if StafUser.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" sudah ada.'))
            return

        user = StafUser.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name='Administrator',
            last_name='MyStaf',
            role='admin',
        )
        self.stdout.write(self.style.SUCCESS(
            f'Superuser "{username}" berhasil dibuat.\n'
            f'  URL Admin: http://localhost:8000/admin/\n'
            f'  Username : {username}\n'
            f'  Password : {password}\n'
            f'  GANTI PASSWORD SETELAH LOGIN PERTAMA!'
        ))
