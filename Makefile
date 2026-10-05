# ফাইল: Makefile
# এই ফাইলটি ISP-BCRM প্রজেক্টের common development commands সহজে চালানোর জন্য।

.PHONY: help setup run stop migrate createsuperuser shell test

# Default target
help:
	@echo "ISP-BCRM Project Commands:"
	@echo "  make setup          - প্রথমবার setup করুন"
	@echo "  make run            - Docker-এ সব service চালু করুন"
	@echo "  make stop           - সব service বন্ধ করুন"
	@echo "  make migrate        - Database migration চালান"
	@echo "  make superuser      - Admin user তৈরি করুন"
	@echo "  make shell          - Django shell খুলুন"
	@echo "  make logs           - Service logs দেখুন"
	@echo "  make test           - Tests চালান"

# প্রথমবার setup
setup:
	cp backend/.env.example backend/.env
	@echo "backend/.env ফাইল তৈরি হয়েছে। নিজের তথ্য দিয়ে পূরণ করুন।"

# Docker-এ সব service চালু করা
run:
	docker-compose up -d
	@echo "সব service চালু হয়েছে। http://localhost:8000 এ access করুন।"

# সব service বন্ধ করা
stop:
	docker-compose down

# Database migration চালানো
migrate:
	docker-compose exec backend python manage.py migrate

# Admin user তৈরি করা
superuser:
	docker-compose exec backend python manage.py createsuperuser

# Django shell
shell:
	docker-compose exec backend python manage.py shell

# Service logs দেখা
logs:
	docker-compose logs -f backend

# Tests চালানো
test:
	docker-compose exec backend python manage.py test

# Database reset (সতর্কতা: সব data মুছে যাবে)
db-reset:
	docker-compose down -v
	docker-compose up -d db redis
	@echo "Database reset হয়েছে।"
