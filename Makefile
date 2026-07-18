.PHONY: up down logs backend-shell rebuild-backend rebuild-frontend

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend-shell:
	docker compose exec backend bash

rebuild-backend:
	docker compose up --build backend

rebuild-frontend:
	docker compose up --build frontend
