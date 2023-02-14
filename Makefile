PYTHON ?= python3
VENV_DIR ?= .build-venv
DIST_DIR ?= dist
SHELL := /bin/bash

msg = @echo -e "\e[1;34m$(1)\e[0m";

ifeq ($(V),1)
	Q =
else
	Q = @
	MAKEFLAGS += --no-print-directory
endif

.PHONY: all
all: $(DIST_DIR)/retsnoop $(DIST_DIR)/network_tracing

$(DIST_DIR)/network_tracing: network_tracing setup.py MANIFEST.in requirements.txt $(DIST_DIR)/retsnoop
	$(call msg,Building package for distribution)
	$(Q)if [[ ! -d "$(VENV_DIR)" ]]; then $(PYTHON) -m venv --system-site-packages "$(VENV_DIR)"; fi
	$(Q)cp -f "$(DIST_DIR)/retsnoop" network_tracing/daemon/tracing/probes/retsnoop
	$(Q)source "$(VENV_DIR)/bin/activate" && pip install -r requirements.txt && pyproject-build --outdir "$(DIST_DIR)/network_tracing"

$(DIST_DIR)/retsnoop: retsnoop
	$(call msg,Building retsnoop)
	$(Q)make -C retsnoop/src/
	$(Q)mkdir -p "$(DIST_DIR)"
	$(Q)cp -f retsnoop/src/retsnoop "$(DIST_DIR)/retsnoop"

.PHONY: clean
clean:
	$(call msg,Cleaning)
	$(Q)rm -rf $(DIST_DIR)
	$(Q)rm -rf $(VENV_DIR)
	$(Q)make -C retsnoop/src/ clean
