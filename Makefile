PYTHON ?= python3
VENV_DIR ?= .build-venv
DIST_DIR ?= dist
BCC_TAG ?= v0.26.0

SHELL := /bin/bash

msg = @echo -e "\e[1;34m$(1)\e[0m";

ifeq ($(V),1)
	Q =
else
	Q = @
	MAKEFLAGS += --no-print-directory
endif

.PHONY: all
all: distribution images operations

.PHONY: distribution
distribution: $(DIST_DIR)/network_tracing

$(DIST_DIR)/network_tracing: network_tracing setup.py MANIFEST.in requirements.txt $(DIST_DIR)/retsnoop/retsnoop
	$(call msg,Initializing build environment)
	$(Q)if [[ ! -d "$(VENV_DIR)" ]]; then $(PYTHON) -m venv --system-site-packages "$(VENV_DIR)"; fi
	$(Q)cp -f "$(DIST_DIR)/retsnoop/retsnoop" network_tracing/daemon/tracing/probes/retsnoop
	$(call msg,Building wheels for distribution)
	$(Q)rm -rf "$(DIST_DIR)/network_tracing"
	$(Q)source "$(VENV_DIR)/bin/activate" && pip install -r requirements.txt && pyproject-build --outdir "$(DIST_DIR)/network_tracing" --wheel

$(DIST_DIR)/retsnoop/retsnoop: retsnoop
	$(call msg,Building retsnoop)
	$(Q)make -C retsnoop/src/
	$(call msg,Copying retsnoop)
	$(Q)mkdir -p "$(DIST_DIR)/retsnoop"
	$(Q)cp -f retsnoop/src/retsnoop "$(DIST_DIR)/retsnoop/retsnoop"

.PHONY: images
images: $(DIST_DIR)/network_tracing-images.tar

$(DIST_DIR)/network_tracing-images.tar: $(DIST_DIR)/network_tracing ops/build
	$(call msg,Building images)
	$(Q)docker build --tag network_tracing:latest --file ops/build/Dockerfile --build-arg "BCC_TAG=$(BCC_TAG)" --build-arg "DIST_DIR=$(DIST_DIR)/network_tracing" .
	$(call msg,Saving images to $(DIST_DIR)/network_tracing-images.tar)
	$(Q)rm -f "$(DIST_DIR)/network_tracing-images.tar"
	$(Q)docker save --output "$(DIST_DIR)/network_tracing-images.tar" network_tracing:latest

.PHONY: operations
operations: $(DIST_DIR)/network_tracing-ops

$(DIST_DIR)/network_tracing-ops: ops/deployment
	$(call msg,Copying config for operations)
	$(Q)rm -rf "$(DIST_DIR)/network_tracing-ops"
	$(Q)mkdir -p "$(DIST_DIR)"
	$(Q)cp -rf ops/deployment "$(DIST_DIR)/network_tracing-ops"

.PHONY: clean
clean:
	$(call msg,Cleaning)
	$(Q)rm -rf $(DIST_DIR)
	$(Q)rm -rf $(VENV_DIR)
	$(Q)make -C retsnoop/src/ clean
