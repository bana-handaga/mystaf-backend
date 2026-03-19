# ============================================================
# MyStaf — Makefile
# Cara pakai: make <perintah>
# ============================================================

BACKEND_DIR  = backend
FRONTEND_DIR = frontend
BACKEND_PORT = 8001
FRONTEND_PORT= 4200

.PHONY: help local prod build deploy setup-local

# ──────────────────────────────────────────────
# Default: tampilkan bantuan
# ──────────────────────────────────────────────
help:
	@echo ""
	@echo "  MyStaf — Perintah yang tersedia:"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup-local       Siapkan .env untuk LOCAL dari .env.local"
	@echo "    make setup-prod        Siapkan .env untuk PRODUCTION dari .env.production"
	@echo ""
	@echo "  Menjalankan (lokal):"
	@echo "    make backend           Jalankan Django dev server (port $(BACKEND_PORT))"
	@echo "    make frontend          Jalankan Angular dev server (port $(FRONTEND_PORT))"
	@echo "    make local             Jalankan backend + frontend bersamaan"
	@echo ""
	@echo "  Build & Deploy:"
	@echo "    make build             Build Angular untuk produksi"
	@echo "    make deploy            Build + push ke GitLab (origin)"
	@echo "    make deploy-all        Build + push ke GitLab + GitHub"
	@echo ""
	@echo "  Lainnya:"
	@echo "    make migrate           Jalankan migrasi database"
	@echo "    make import-users      Import user dari GitLab UMS"
	@echo "    make sync-users        Import + update user dari GitLab UMS"
	@echo ""

# ──────────────────────────────────────────────
# Setup environment
# ──────────────────────────────────────────────
setup-local:
	@echo ">> Menggunakan environment LOCAL..."
	cp $(BACKEND_DIR)/.env.local $(BACKEND_DIR)/.env
	@echo "   ✓ $(BACKEND_DIR)/.env → dari .env.local"
	@echo "   Database  : SQLite"
	@echo "   API proxy : http://localhost:$(FRONTEND_PORT) → localhost:$(BACKEND_PORT)"

setup-prod:
	@echo ">> Menggunakan environment PRODUCTION..."
	cp $(BACKEND_DIR)/.env.production $(BACKEND_DIR)/.env
	@echo "   ✓ $(BACKEND_DIR)/.env → dari .env.production"
	@echo "   !! Pastikan SECRET_KEY dan DB_PASSWORD sudah diisi di .env !!"
	@echo "   API URL   : https://api.dsti-ums.id"
	@echo "   Frontend  : https://dev.dsti-ums.id"

# ──────────────────────────────────────────────
# Development server
# ──────────────────────────────────────────────
backend:
	@echo ">> Menjalankan Django backend (http://localhost:$(BACKEND_PORT))..."
	cd $(BACKEND_DIR) && python3 manage.py runserver $(BACKEND_PORT)

frontend:
	@echo ">> Menjalankan Angular frontend (http://localhost:$(FRONTEND_PORT))..."
	cd $(FRONTEND_DIR) && ng serve --port $(FRONTEND_PORT)

local:
	@echo ">> Menjalankan backend + frontend..."
	@make setup-local
	cd $(BACKEND_DIR) && python3 manage.py runserver $(BACKEND_PORT) &
	cd $(FRONTEND_DIR) && ng serve --port $(FRONTEND_PORT)

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
migrate:
	cd $(BACKEND_DIR) && python3 manage.py migrate

import-users:
	@echo ">> Import user dari GitLab UMS (dry-run dulu)..."
	cd $(BACKEND_DIR) && python3 manage.py import_gitlab_users --dry-run
	@read -p "   Lanjutkan import? [y/N] " ans; \
	  if [ "$$ans" = "y" ] || [ "$$ans" = "Y" ]; then \
	    cd $(BACKEND_DIR) && python3 manage.py import_gitlab_users; \
	  fi

sync-users:
	cd $(BACKEND_DIR) && python3 manage.py import_gitlab_users --update

# ──────────────────────────────────────────────
# Build & Deploy
# ──────────────────────────────────────────────
build:
	@echo ">> Build Angular untuk produksi..."
	cd $(FRONTEND_DIR) && ng build
	@echo "   ✓ Output: $(FRONTEND_DIR)/public/"

deploy: build
	@echo ">> Push ke GitLab UMS (origin)..."
	cd $(FRONTEND_DIR) && git add public/ && \
	  git commit -m "build: update production bundle $(shell date '+%Y-%m-%d %H:%M')" 2>/dev/null || true && \
	  git push origin
	cd $(BACKEND_DIR) && git push origin
	@echo "   ✓ Deploy selesai → https://dev.dsti-ums.id"

deploy-all: build
	@echo ">> Push ke GitLab UMS + GitHub..."
	cd $(FRONTEND_DIR) && git add public/ && \
	  git commit -m "build: update production bundle $(shell date '+%Y-%m-%d %H:%M')" 2>/dev/null || true && \
	  git push origin && git push github
	cd $(BACKEND_DIR) && git push origin && git push github
	@echo "   ✓ Deploy selesai ke GitLab + GitHub"
