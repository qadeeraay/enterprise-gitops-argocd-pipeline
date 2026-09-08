.PHONY: test lint render simulate clean help

help:
	@echo "Available commands:"
	@echo "  make test      - Run microservice unit tests"
	@echo "  make lint      - Lint Helm chart and validate syntax"
	@echo "  make render    - Render Helm templates across dev, staging, prod"
	@echo "  make simulate  - Simulate automated metric-driven canary rollback"
	@echo "  make clean     - Remove temporary cache files"

test:
	python3 -m unittest discover -s tests -v

lint:
	helm lint charts/payment-gateway

render:
	bash tests/validate_helm.sh

simulate:
	python3 tests/simulate_canary_rollback.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
