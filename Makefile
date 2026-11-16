.PHONY: install ui test dev run seed clean docker

install:
	pip install -r backend/requirements.txt
	npm --prefix frontend install --no-audit --no-fund

ui:
	npm --prefix frontend run build

test:
	cd backend && python -m pytest

demo:
	cd backend && python -m app.seed

run: ui
	cd backend && uvicorn app.main:app --reload

dev:
	@echo "two terminals:"
	@echo "  cd backend && uvicorn app.main:app --reload"
	@echo "  npm --prefix frontend run dev"

docker:
	docker build -t preppilot . && docker run -p 8000:8000 preppilot

clean:
	rm -f backend/preppilot.db backend/tests/test_preppilot.db
	rm -rf frontend/dist frontend/node_modules .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
