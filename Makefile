.PHONY: help backend-install backend-dev backend-test frontend-install frontend-dev seed-demo rebuild-pipeline docker-up docker-down

help:
	@echo "OrbiFlare -- common commands"
	@echo "  make backend-install     Create backend venv and install dependencies"
	@echo "  make backend-dev         Run the FastAPI dev server (auto-seeds demo data)"
	@echo "  make backend-test        Run backend pytest suite"
	@echo "  make frontend-install    Install frontend npm dependencies"
	@echo "  make frontend-dev        Run the Next.js dev server"
	@echo "  make seed-demo           Reset DB and seed the DEMO/SYNTHETIC scenario"
	@echo "  make rebuild-pipeline    Re-run the full intelligence pipeline"
	@echo "  make docker-up           Start Postgres+PostGIS, backend and frontend via Docker"
	@echo "  make docker-down         Stop the Docker stack"

backend-install:
	cd backend && python -m venv .venv && ./.venv/bin/pip install -r requirements.txt

backend-dev:
	cd backend && ./.venv/bin/uvicorn app.main:app --reload --port 8000

backend-test:
	cd backend && ./.venv/bin/pytest -q

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

seed-demo:
	cd backend && ../.venv/bin/python ../scripts/seed_demo.py || python scripts/seed_demo.py

rebuild-pipeline:
	python scripts/rebuild_pipeline.py --mode demo

docker-up:
	docker compose up --build

docker-down:
	docker compose down
