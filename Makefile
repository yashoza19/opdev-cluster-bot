IMAGE ?= quay.io/example/opdev-cluster-bot
TAG ?= latest
PLATFORM ?= linux/amd64
NAMESPACE ?= opdev-cluster-bot
PYTHON ?= python3.12
VENV ?= .venv

.PHONY: help venv install test lint run dry-run docker-build docker-push deploy undeploy clean

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

venv: ## Create local virtualenv
	$(PYTHON) -m venv $(VENV)

install: venv ## Install package + dev deps into venv
	$(VENV)/bin/pip install -U pip
	$(VENV)/bin/pip install -e ".[dev]"

test: ## Run unit tests
	$(VENV)/bin/pytest -q

run: ## Run Socket Mode bot (requires env / .env exported)
	$(VENV)/bin/opdev-cluster-bot

dry-run: ## Run bot with DRY_RUN=true
	DRY_RUN=true $(VENV)/bin/opdev-cluster-bot

remind: ## Run EOD remind job once
	$(VENV)/bin/opdev-remind-hibernate

weekend: ## Run weekend hibernate job once
	$(VENV)/bin/opdev-weekend-hibernate

monday: ## Run Monday resume job once
	$(VENV)/bin/opdev-monday-resume

docker-build: ## Build linux/amd64 image locally (buildx --load)
	docker buildx build --platform $(PLATFORM) -t $(IMAGE):$(TAG) --load .

docker-push: ## Build and push linux/amd64 image (buildx --push)
	docker buildx build --platform $(PLATFORM) -t $(IMAGE):$(TAG) --push .

deploy: ## Apply manifests to current kube context
	oc apply -f deploy/namespace.yaml
	oc apply -f deploy/rbac.yaml
	oc apply -f deploy/configmap.yaml
	oc apply -f deploy/deployment.yaml
	oc apply -f deploy/cronjobs.yaml

undeploy: ## Delete bot Deployment/CronJobs (keeps secrets/namespaces)
	oc -n $(NAMESPACE) delete deployment opdev-cluster-bot --ignore-not-found
	oc -n $(NAMESPACE) delete cronjob -l app.kubernetes.io/name=opdev-cluster-bot --ignore-not-found

clean: ## Remove local venv and caches
	rm -rf $(VENV) .pytest_cache .coverage htmlcov *.egg-info src/*.egg-info
