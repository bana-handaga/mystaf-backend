"""
Management command: import_gitlab_users
Mengambil user aktif dari GitLab dan membuat akun staf programmer.
User yang sudah ada (berdasarkan gitlab_username) di-update, bukan duplikat.
"""
import re
import gitlab
from django.core.management.base import BaseCommand
from gitlab_analysis.models import GitLabConfig
from accounts.models import StafUser

# Username yang dilewati (bot, sistem, admin)
SKIP_USERNAMES = {
    'root', 'gits', 'btiedu', 'bhp', 'pesma',
    'repoinovasifrontend', 'kemal',
}
SKIP_PATTERNS = [
    r'^group_\d+_bot_',   # GitLab group bots
    r'_bot$',
    r'^bot_',
]

DEFAULT_PASSWORD = 'StafDSTI@2025'


def should_skip(username: str, name: str) -> bool:
    if username.lower() in SKIP_USERNAMES:
        return True
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, username, re.IGNORECASE):
            return True
    return False


def split_name(full_name: str):
    """Pisahkan nama lengkap menjadi first_name dan last_name."""
    # Hapus gelar akademik di belakang (S.Kom., M.T., dll)
    clean = re.sub(r',?\s+(S\.Kom|S\.T|M\.T|M\.Sc|M\.Cs|A\.Md|S\.Pd|M\.Pd)\.*$', '', full_name, flags=re.IGNORECASE).strip()
    parts = clean.split(' ', 1)
    first = parts[0]
    last = parts[1] if len(parts) > 1 else ''
    return first, last


class Command(BaseCommand):
    help = 'Import user aktif dari GitLab sebagai staf programmer'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Tampilkan tanpa menyimpan')
        parser.add_argument('--update', action='store_true', help='Update data user yang sudah ada')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        do_update = options['update']

        config = GitLabConfig.objects.filter(is_active=True).first()
        if not config:
            self.stderr.write('ERROR: Konfigurasi GitLab belum diatur.')
            return

        self.stdout.write(f'Menghubungkan ke {config.url}...')
        gl = gitlab.Gitlab(config.url, private_token=config.private_token)
        gl.auth()
        self.stdout.write(self.style.SUCCESS('Koneksi berhasil.'))

        users = gl.users.list(active=True, all=True)
        self.stdout.write(f'Ditemukan {len(users)} user aktif di GitLab.\n')

        created = 0
        updated = 0
        skipped = 0
        skipped_names = []

        for gl_user in users:
            username = gl_user.username
            name = gl_user.name
            email = getattr(gl_user, 'email', '') or f'{username}@gitlab.local'

            if should_skip(username, name):
                skipped += 1
                skipped_names.append(username)
                continue

            first_name, last_name = split_name(name)

            if dry_run:
                exists = StafUser.objects.filter(gitlab_username=username).exists()
                status = '[EXISTS]' if exists else '[NEW]'
                self.stdout.write(f'  {status} {username:25} | {name}')
                continue

            # Cek apakah sudah ada berdasarkan gitlab_username
            existing = StafUser.objects.filter(gitlab_username=username).first()

            if existing:
                if do_update:
                    existing.first_name = first_name
                    existing.last_name = last_name
                    if email and '@gitlab.local' not in email:
                        existing.email = email
                    existing.save()
                    updated += 1
                    self.stdout.write(f'  [UPDATE] {username:25} | {name}')
                else:
                    self.stdout.write(f'  [SKIP]   {username:25} | sudah ada')
                continue

            # Buat user baru — gunakan gitlab_username sebagai username sistem
            # Hindari konflik dengan username yang sudah ada
            sys_username = username
            if StafUser.objects.filter(username=sys_username).exists():
                sys_username = f'gl_{username}'

            user = StafUser(
                username=sys_username,
                first_name=first_name,
                last_name=last_name,
                email=email if email and '@gitlab.local' not in email else f'{username}@dsti.ums.ac.id',
                gitlab_username=username,
                role='programmer',
                is_active=True,
            )
            user.set_password(DEFAULT_PASSWORD)
            user.save()
            created += 1
            self.stdout.write(f'  [CREATE] {username:25} | {name}')

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN — tidak ada yang disimpan.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Selesai: {created} dibuat, {updated} diupdate.'))
        self.stdout.write(f'Dilewati ({skipped}): {", ".join(skipped_names)}')
