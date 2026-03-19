# Dokumen Pengembangan MyStaf
**Tanggal:** 19 Maret 2026
**Sistem:** MyStaf — Monitoring Aktivitas Staf Programmer DSTI UMS
**Stack:** Django 5.2 (Backend) + Angular 21 + Angular Material (Frontend)

---

## 1. Gambaran Umum Sistem

MyStaf adalah sistem monitoring aktivitas staf programmer berbasis data dari GitLab UMS (`https://gitlab.ums.ac.id`). Sistem mengumpulkan data commit, push event, merge request, issue, dan komentar untuk ditampilkan dalam dashboard analitik.

### Arsitektur
```
[GitLab UMS] ──sync──► [Django API] ──REST──► [Angular Frontend]
                              │
                         [MySQL / SQLite]
```

### URL Produksi
| Komponen | URL |
|----------|-----|
| Frontend | https://dev.dsti-ums.id |
| Backend API | https://api.dsti-ums.id |
| GitLab | https://gitlab.ums.ac.id |

### Repository
| Repo | GitLab UMS (Primary) | GitHub (Backup) |
|------|----------------------|-----------------|
| Backend | `gitlab.ums.ac.id/bh014/mystaf-backend` | `github.com/bana-handaga/mystaf-backend` |
| Frontend | `gitlab.ums.ac.id/bh014/mystaf-frontend` | `github.com/bana-handaga/mystaf-frontend` |

---

## 2. Fitur yang Dikembangkan

### 2.1 Halaman Dashboard
- Ringkasan aktivitas tim: total commit, push event, merge request, issue, komentar
- Grafik aktivitas harian
- Tabel kontributor teratas

### 2.2 Halaman Staf
- Daftar semua staf programmer dengan total aktivitas dan commit
- Pencarian nama/username secara real-time (debounce 400ms)
- Sortir kolom: nama, username, GitLab, aktivitas, commits
- Filter periode: 7 / 14 / 30 / 90 hari
- Badge aktivitas berwarna: hijau (≥50), kuning (10–49), merah (<10)
- Tombol profil ke detail staf

### 2.3 Halaman Detail Staf
- Avatar inisial, nama lengkap, gitlab username, role
- Kartu statistik: Commits, Push Events, Merge Requests, Issues, Komentar
- Grafik batang aktivitas harian
- Chip proyek aktif dalam periode
- Tombol **Sync Aktivitas** dengan indikator progress

### 2.4 Halaman Proyek / Apps
- Daftar proyek GitLab aktif dalam periode (filter by `last_activity_at`)
- Badge commit berwarna, badge kontributor
- Sortir client-side: nama, commits, kontributor, aktivitas terakhir
- Pencarian nama proyek/namespace
- Chip visibilitas: private/internal/public
- Tombol **Sync Proyek** dengan auto-sync commit proyek baru

### 2.5 Halaman Detail Proyek
- Header proyek dengan link ke GitLab
- Kartu stat: Total Commits, Kontributor, Aktivitas Terakhir
- Tabel kontributor dengan progress bar commit relatif
- Rank dengan emoji 🥇🥈🥉
- Tombol **Sync Commits** per proyek

### 2.6 Halaman Commit Message
- Tabel semua commit dalam periode
- Filter: pencarian teks, proyek, staf
- Link ke GitLab per commit

### 2.7 Halaman Commit Analisis
- Breakdown kategori commit: fix, feature, refactor, docs, config, test, remove, merge, other
- Ringkasan per staf dan per staf-proyek
- Kategori dominan per kombinasi staf-proyek

### 2.8 Halaman Komentar
- Tabel komentar issue dan commit dari GitLab
- Filter: pencarian, proyek, author, status issue, tipe komentar
- Link ke issue/commit asli di GitLab

### 2.9 Halaman Laporan Pimpinan *(Baru)*
- Laporan manajemen berbasis NLP sederhana (tanpa library ML berat)
- **Analisis per staf:**
  - Total commit, push event, merge request, issue
  - Kategori aktivitas dominan
  - Deteksi topik teknis (API/Backend, Frontend/UI, Database, Auth, Testing, DevOps, Performa, Fitur Bisnis)
  - Ekstraksi kata kunci dari pesan commit (TF-IDF/word frequency)
  - Daftar proyek yang terlibat
  - **Narasi otomatis** dalam Bahasa Indonesia
- **Ringkasan tim:**
  - Staf aktif vs total staf
  - Topik teknis tim (bar chart)
  - Keyword cloud
- **Fitur cetak/PDF** — layout khusus print dengan header/footer
- Periode: 7 / 14 / 30 / 90 hari

---

## 3. Perbaikan Bug yang Dilakukan

### 3.1 Indikator Sinkronisasi Tidak Muncul
**Gejala:** Tombol sync berubah disabled tapi tidak ada visual progress.
**Root cause:** Angular tidak me-render perubahan state `syncing=true` sebelum HTTP call async dimulai.
**Fix:** Tambah `ChangeDetectorRef.detectChanges()` setelah `this.syncing = true` di `project-detail` dan `staf-detail`.
**Solusi akhir:** Ganti `MatSnackBar` dengan fixed-position CSS banner (`position: fixed; z-index: 99999; bottom: 24px`) yang lebih reliable.

### 3.2 Tabel Tidak Responsive di Mobile
**Gejala:** Tabel terpotong di layar kecil, tidak bisa di-scroll horizontal.
**Root cause:** Angular Material `mat-card` (MDC) memiliki `overflow: hidden` yang mengclip konten scroll.
**Fix:**
```scss
/* styles.scss */
mat-card, .mat-mdc-card, .mdc-card { overflow: visible !important; }
mat-card-content, .mat-mdc-card-content { overflow: visible !important; }

.table-scroll {
  overflow-x: auto !important;
  -webkit-overflow-scrolling: touch;
  width: 100%;
  display: block;
}
.table-scroll table, .table-scroll mat-table {
  min-width: 480px;
}
```
Kolom yang disembunyikan di mobile (via media query):
- Project-detail: `rank`, `first_commit`, `last_commit`
- Staf: `no`, `email`, `gitlab`
- Projects: `no`, `last_activity`, `visibility`

### 3.3 404 saat Browser Refresh (SPA Routing)
**Gejala:** Refresh halaman `/dashboard` atau `/staf/1` mengembalikan 404.
**Root cause:** Apache tidak mengenal Angular route — mencari file fisik yang tidak ada.
**Fix:** `.htaccess` dengan `RewriteRule`:
```apache
Options -MultiViews
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^ index.html [QSA,L]
```
File `.htaccess` didaftarkan sebagai asset di `angular.json` agar ikut di-build.

### 3.4 Sync Diam-diam Gagal (Silent Failure)
**Gejala:** Sync berhasil (banner hijau, `0 commit baru`) tapi data tidak update.
**Root causes:**
1. `except Exception: return 0` di `sync_project_commits` — semua error GitLab API (auth gagal, rate limit, timeout) dilaporkan sebagai sukses
2. Frontend tidak mengecek field `status: 'error'` di response — selalu tampil "Selesai"
3. `datetime.now()` diformat dengan suffix `Z` (UTC) padahal waktu lokal → parameter `since` bisa salah

**Fix backend (`services.py`):**
```python
# Sebelum (salah):
since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
try:
    commits = gl_project.commits.list(since=since, all=True)
except Exception:
    return 0  # ← silent failure

# Sesudah (benar):
from datetime import timezone as dt_timezone
since = (datetime.now(dt_timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
try:
    commits = gl_project.commits.list(since=since, all=True, with_stats=False)
except Exception as e:
    raise ValueError(f"Gagal mengambil commits dari GitLab: {e}")  # ← propagate error
```

**Fix frontend:** Cek `status === 'error'` di response dan tampilkan pesan error spesifik.

### 3.5 Staf Matching Salah pada Commit Sync
**Gejala:** Commit tersimpan tapi tidak terhubung ke staf yang benar.
**Root cause:** Username diambil dari prefix email (`john.doe@ums.ac.id` → `john.doe`), bukan gitlab_username asli.
**Fix:** Lookup staf berdasarkan email dulu, baru fallback ke prefix:
```python
staf_by_email = {s.email.lower(): s for s in all_staf if s.email}
staf = staf_by_email.get(author_email) or staf_by_username.get(email_prefix)
```

### 3.6 Proyek Baru Tidak Muncul di Daftar
**Gejala:** Proyek yang baru dibuat hari ini tidak tampil meski sudah sync.
**Root causes:**
1. Filter `commit_count__gt=0` — proyek tanpa commit di DB tidak ditampilkan
2. `Sync Proyek` hanya sync metadata, bukan commits

**Fix `ProjectListView`:**
```python
# Sebelum: .filter(commit_count__gt=0)
# Sesudah:
.filter(last_activity_at__gte=since)
.order_by('-commit_count', '-last_activity_at')
```

**Fix `SyncProjectsView`:** Auto-sync commits untuk proyek baru (commit_count=0 di DB tapi punya activity):
```python
new_projects = GitLabProject.objects.annotate(
    commit_count=Count('commits')
).filter(commit_count=0, last_activity_at__gte=since)
for proj in new_projects:
    service.sync_project_commits(proj, days)
```

---

## 4. Konfigurasi dan Setup

### 4.1 Database
| Environment | Database |
|-------------|----------|
| Production | MySQL 8.0, charset `utf8mb4` |
| Development (lokal) | SQLite (`db.sqlite3`) |

Kontrol via environment variable di `.env`:
```env
USE_SQLITE=true   # lokal
USE_SQLITE=false  # produksi (default MySQL)
```

### 4.2 Environment Variables Backend (`.env`)
```env
SECRET_KEY=...
DEBUG=True/False
ALLOWED_HOSTS=localhost,127.0.0.1,api.dsti-ums.id
USE_SQLITE=false
DB_NAME=mystaf
DB_USER=...
DB_PASSWORD=...
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 4.3 Angular Environment
| File | Digunakan saat |
|------|----------------|
| `environment.ts` | `ng serve` (dev) — `apiBase: ''` (relative, proxy) |
| `environment.prod.ts` | `ng build` (prod) — `apiBase: 'https://api.dsti-ums.id'` |

### 4.4 Proxy Development (`proxy.conf.json`)
```json
{
  "/api": {
    "target": "http://localhost:8001",
    "secure": false,
    "changeOrigin": true
  }
}
```
Angular dev server otomatis membaca proxy config ini via `angular.json`.

---

## 5. Cara Menjalankan Lokal

### Prasyarat
- Python 3.12+ dengan package: `django`, `djangorestframework`, `python-gitlab`, `whitenoise`, dll
- Node.js + Angular CLI (`ng`)
- SQLite (sudah built-in Python)

### Backend
```bash
cd backend
# .env sudah dikonfigurasi dengan USE_SQLITE=true
python3 manage.py runserver 8001
```

### Frontend
```bash
cd frontend
ng serve
# Buka: http://localhost:4200
```

### Login Lokal
| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin |
| staf lain | `StafDSTI@2025` | Programmer |

---

## 6. Import Data User dari GitLab

Management command untuk import/update staf dari GitLab UMS:

```bash
# Preview tanpa menyimpan
python3 manage.py import_gitlab_users --dry-run

# Import semua user baru
python3 manage.py import_gitlab_users

# Import + update data yang sudah ada
python3 manage.py import_gitlab_users --update
```

**Logika:**
- Cocokkan existing user via `gitlab_username`
- Skip: `root`, `gits`, group bots, akun sistem
- Pisahkan nama lengkap → `first_name` + `last_name` (hapus gelar: S.Kom., M.T., dll)
- Password default staf baru: `StafDSTI@2025`

**Hasil import:** 86 staf programmer dengan `gitlab_username` dari 91 user aktif GitLab (5 dilewati: bot/sistem).

---

## 7. Endpoint API Backend

Base URL: `https://api.dsti-ums.id/api/`

### Auth
| Method | Endpoint | Keterangan |
|--------|----------|------------|
| POST | `/auth/login/` | Login, dapat token |
| POST | `/auth/logout/` | Logout |
| GET | `/auth/profile/` | Profil user login |
| GET | `/auth/staff/` | Daftar staf (query: `days`, `search`, `order_by`) |

### GitLab
| Method | Endpoint | Keterangan |
|--------|----------|------------|
| GET | `/gitlab/projects/` | Daftar proyek aktif |
| POST | `/gitlab/projects/sync/` | Sync proyek + auto-sync commit baru |
| GET | `/gitlab/projects/{id}/` | Detail proyek + kontributor |
| POST | `/gitlab/projects/{id}/sync/` | Sync commit per proyek |
| GET | `/gitlab/summary/{staf_id}/` | Ringkasan aktivitas staf |
| POST | `/gitlab/sync/{staf_id}/` | Sync aktivitas staf |
| GET | `/gitlab/commits/` | Daftar commit message |
| GET | `/gitlab/commits/analysis/` | Analisis kategori commit |
| GET | `/gitlab/comments/` | Daftar komentar |
| GET | `/gitlab/reports/` | Laporan manajemen (NLP) |
| GET | `/gitlab/diagnostic/` | Test koneksi GitLab |
| GET/POST | `/gitlab/config/` | Konfigurasi GitLab token |

---

## 8. Teknik NLP pada Laporan Manajemen

Implementasi di `gitlab_analysis/report_service.py` menggunakan pure Python (tanpa library ML).

### Ekstraksi Keyword
- Tokenisasi: lowercase, hapus karakter non-alfanumerik, filter kata < 3 huruf
- Stopwords: Bahasa Indonesia + Inggris + noise git (commit, merge, fix, dll)
- Word frequency menggunakan `collections.Counter`

### Deteksi Topik Teknis
8 kategori dengan keyword matching:
| Topik | Contoh Keyword |
|-------|----------------|
| API / Backend | api, endpoint, rest, django, service, controller |
| Frontend / UI | angular, react, component, css, responsive, template |
| Database | migration, query, mysql, schema, orm, index |
| Auth / Keamanan | auth, token, jwt, permission, role, password |
| Testing / QA | test, spec, coverage, pytest, selenium |
| DevOps / CI/CD | docker, deploy, pipeline, nginx, workflow |
| Performa | cache, optimize, lazy, paginate, async |
| Fitur Bisnis | report, dashboard, export, pdf, notif, payment |

### Klasifikasi Commit
9 kategori berdasarkan keyword di pesan commit:
`fix` · `feature` · `refactor` · `docs` · `config` · `test` · `remove` · `merge` · `other`

### Generasi Narasi
Teks deskriptif otomatis dalam Bahasa Indonesia berisi:
- Jumlah commit dan proyek dalam periode
- Aktivitas dominan
- Bidang teknis yang dikerjakan (maks 3 topik)
- Kata kunci populer (maks 5)
- Tambahan: push event, MR, issues

---

## 9. Migrasi Repository

Repositori dipindahkan dari GitHub ke GitLab UMS sebagai primary remote.

```bash
# Status remote saat ini:
# origin  → gitlab.ums.ac.id/bh014/mystaf-* (PRIMARY)
# github  → github.com/bana-handaga/mystaf-*  (BACKUP)

# Push ke GitLab (default):
git push

# Push ke keduanya:
git push origin && git push github
```

---

## 10. Struktur Direktori

```
mystaf/
├── backend/
│   ├── accounts/
│   │   ├── models.py          # StafUser model
│   │   └── management/commands/
│   │       ├── setup_initial.py
│   │       └── import_gitlab_users.py   ← Baru
│   ├── gitlab_analysis/
│   │   ├── models.py          # GitLabActivity, GitLabProject, ProjectCommit, IssueComment
│   │   ├── services.py        # GitLabService (sync logic)
│   │   ├── report_service.py  # NLP report generation ← Baru
│   │   ├── views.py           # REST API views
│   │   └── urls.py
│   └── backend/
│       └── settings.py        # USE_SQLITE support ← Diubah
│
└── frontend/
    ├── src/
    │   ├── environments/
    │   │   ├── environment.ts       ← Baru (dev)
    │   │   └── environment.prod.ts  ← Baru (prod)
    │   ├── app/
    │   │   ├── app.ts              # Layout + sidenav + bottom tab
    │   │   ├── app.routes.ts       # Routing
    │   │   ├── core/services/
    │   │   │   ├── auth.service.ts
    │   │   │   ├── gitlab.service.ts
    │   │   │   ├── project.service.ts
    │   │   │   └── comment.service.ts
    │   │   └── pages/
    │   │       ├── dashboard/
    │   │       ├── staf/
    │   │       ├── staf-detail/
    │   │       ├── projects/
    │   │       ├── project-detail/
    │   │       ├── commits/
    │   │       ├── commit-analysis/
    │   │       ├── comments/
    │   │       ├── laporan/         ← Baru
    │   │       ├── profile/
    │   │       └── login/
    │   ├── styles.scss             # Global: table scroll, mat-card overflow fix
    │   └── .htaccess               # SPA routing fix untuk Apache
    ├── proxy.conf.json             ← Baru (local dev proxy)
    └── angular.json
```

---

## 11. Commits Hari Ini

### Backend
| Hash | Deskripsi |
|------|-----------|
| `24a247e` | Fix project list hiding new projects with no synced commits |
| `0b599ed` | Add import_gitlab_users management command |
| `195c422` | Add USE_SQLITE option for local development |
| `68e2e33` | Fix silent sync failures and timezone bug |
| `bca2196` | Add management report feature with NLP analysis |

### Frontend
| Hash | Deskripsi |
|------|-----------|
| `1e6d4e6` | Add environment config for local development |
| `745964a` | Fix sync error handling in project-detail and staf-detail |
| `79996c3` | Add Laporan (management report) page |
| `a6f6ac6` | Fix responsive table horizontal scroll on mobile |
| `11d1223` | Force change detection on sync start |
| `19fac15` | Replace MatSnackBar with fixed-position CSS banner |

---

*Dokumen ini dibuat otomatis berdasarkan log pengembangan MyStaf — 19 Maret 2026*
