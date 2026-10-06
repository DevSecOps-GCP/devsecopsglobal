.PHONY: up down logs test test-backend test-frontend lint fmt

up:            ## run the whole stack on http://localhost:8080
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend gateway

test: test-backend test-frontend

test-backend:  ## needs `docker compose up -d db redis`
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run typecheck

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .
