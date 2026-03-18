from django.core.management.base import BaseCommand
from gitlab_analysis.services import GitLabService
from accounts.models import StafUser

class Command(BaseCommand):
    help = 'Sinkronisasi aktivitas programmer dari GitLab'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Jumlah hari ke belakang')
        parser.add_argument('--username', default=None, help='Sinkronisasi 1 user saja')

    def handle(self, *args, **options):
        days = options['days']
        username = options['username']

        try:
            service = GitLabService()
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            self.stdout.write('Atur konfigurasi GitLab terlebih dahulu di /admin/ atau via API.')
            return

        if username:
            staf_list = StafUser.objects.filter(username=username)
        else:
            staf_list = StafUser.objects.filter(role='programmer', is_active=True, gitlab_username__isnull=False)

        if not staf_list.exists():
            self.stdout.write(self.style.WARNING('Tidak ada staf programmer dengan gitlab_username.'))
            return

        self.stdout.write(f'Sinkronisasi {staf_list.count()} staf untuk {days} hari terakhir...')
        for staf in staf_list:
            try:
                count = service.sync_staf_activity(staf, days)
                self.stdout.write(self.style.SUCCESS(f'  {staf.username}: {count} aktivitas baru'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  {staf.username}: {e}'))
