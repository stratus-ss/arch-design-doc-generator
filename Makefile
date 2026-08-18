# Arch Design Doc Generator — Makefile
#
# The only interface you need. Run `make` or `make help` to see all targets.
#
# Container targets (build, diagrams, pdfs, etc.) run inside a Podman/Docker
# container so you don't need pandoc, weasyprint, drawio, or stitchmd on the host.
#
# AI preparation targets run on the host because they need your API credentials.
#
# Prerequisites (host):
#   Container targets: podman or docker, make
#   AI targets:        python3, pyyaml, cursor-sdk (or claude/codex CLI)
#
# Quick start:
#   1. make setup CLIENT="Example Client" PROJECT="OCP-V"   # bootstrap project
#   2. Fill in ADR/<client>.md from templates/ADR/   # gitignored working copy
#   3. make build                        # AI draft + stitch + diagrams + PDFs + work items


# ── Python path for host-side targets ────────────────────────────────
export PYTHONPATH := scripts/shared/lib:scripts/health_check:$(PYTHONPATH)

# ── Container engine ─────────────────────────────────────────────────
# Detects podman first, falls back to docker.  Override: make build ENGINE=docker
ENGINE ?= $(shell command -v podman 2>/dev/null || echo docker)
IMAGE  ?= arch-doc-gen

# Hash of Containerfile + scripts/ tree (path + mtime per file).
_SCRIPTS_HASH := $(shell { find scripts Containerfile -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -not -name '*.pyo' -printf '%p %T@\n'; } | sort | sha256sum | cut -d' ' -f1)

_RUN    := $(ENGINE) run --rm -v "$$(pwd)":/workspace:Z --entrypoint /workspace/scripts/entrypoint.sh $(IMAGE)
_RUNOUT := $(ENGINE) run --rm -v "$$(pwd)":/workspace:Z -v "$$(pwd)/output":/output:Z --entrypoint /workspace/scripts/entrypoint.sh $(IMAGE)

# ── Python interpreter ───────────────────────────────────────────────
PYTHON ?= python3
OUTPUT_ROOT ?= output
PROJECT ?= OCP-V
FORCE ?=

# GNU make rejects `--force` as an option (`make: unrecognized option '--force'`).
# Use FORCE=1 or an extra `force` goal: `make build-hld-from-adr FORCE=1`
# or `make build-hld-from-adr force`.
ifneq ($(filter force,$(MAKECMDGOALS)),)
FORCE := 1
endif
_FORCE_ON := $(filter 1 true yes TRUE YES,$(FORCE))

# ── Makefile config ──────────────────────────────────────────────────
.DEFAULT_GOAL := help

# Canned recipe: fail with a usage message if the named variable is empty.
define require
	@if [ -z "$($(1))" ]; then echo "$(if $(2),$(2),Error: set $(1)=...)"; exit 1; fi
endef

# Collect/fetch/merge do not require project.yaml; remind the operator if it is missing.
define warn_missing_project_yaml
	@if [ ! -f project.yaml ]; then \
		echo "Note: project.yaml not found yet — collect/fetch do not require it."; \
		echo "      Run 'make setup CLIENT=\"Your Client Name\" PROJECT=\"HC\"' whenever convenient (not required for this step)."; \
	fi
endef

.PHONY: help force \
        image setup build rebuild publish prepare-and-publish build-hld build-hld-from-adr build-lld \
        diagrams pdfs workitems rvtools status lld-closeness \
        prepare-hld-ai draft-hld-ai-normalize validate-hld-ai-normalize \
        test-hld-ai-repeatability \
        inspect-slots inspect-chunks validate-slots \
        combine-drawio sanitize-diagrams sample-schedule check-annotations package \
        force-image \
        hc-collect hc-push-scripts hc-collect-remote hc-fetch-results hc-merge clean-hc \
        clean clean-build clean-hld clean-lld clean-pdfs clean-diagrams clean-workitems clean-ai clean-setup push

# Extra goal: `make build-hld-from-adr force` (GNU make cannot take --force).
force:
	@:

# ── Help ─────────────────────────────────────────────────────────────

help: ## Show this help
	@echo ""
	@echo "  Arch Design Doc Generator"
	@echo "  ======================"
	@echo ""
	@desc() { awk -v t="$$1" '$$0 ~ "^" t ":[^#]*## " { sub(/^[^#]*## /, ""); print; exit }' $(MAKEFILE_LIST); }; \
	print_target() { d="$$(desc "$$1")"; [ -n "$$d" ] && printf "  \033[36m%-30s\033[0m %s\n" "$$1" "$$d"; }; \
	echo "  Core workflow:"; \
	print_target setup; \
	print_target status; \
	print_target build-hld-from-adr; \
	print_target publish; \
	print_target prepare-and-publish; \
	print_target build; \
	print_target rebuild; \
	echo ""; \
	echo "  HLD AI (host):"; \
	print_target prepare-hld-ai; \
	print_target validate-hld-ai-normalize; \
	print_target test-hld-ai-repeatability; \
	print_target inspect-slots; \
	print_target inspect-chunks; \
	print_target validate-slots; \
	echo ""; \
	echo "  Container/output:"; \
	print_target build-lld; \
	print_target diagrams; \
	print_target pdfs; \
	print_target workitems; \
	print_target rvtools; \
	print_target sample-schedule; \
	echo ""; \
	echo "  Utilities:"; \
	print_target combine-drawio; \
	print_target sanitize-diagrams; \
	print_target check-annotations; \
	print_target package; \
	echo ""; \
	echo "  Health Check (host):"; \
	print_target hc-collect; \
	print_target hc-push-scripts; \
	print_target hc-collect-remote; \
	print_target hc-fetch-results; \
	print_target hc-merge; \
	print_target clean-hc; \
	echo ""; \
	echo "  Maintenance:"; \
	print_target image; \
	print_target force-image; \
	print_target push; \
	print_target clean; \
	print_target clean-build; \
	print_target clean-hld; \
	print_target clean-lld; \
	print_target clean-pdfs; \
	print_target clean-diagrams; \
	print_target clean-workitems; \
	print_target clean-ai; \
	print_target clean-setup
	@echo ""
	@echo "  Quick start:"
	@echo "    1. make setup CLIENT=\"Example Client\" PROJECT=\"OCP-V\""
	@echo "    2. Fill in ADR/<client>.md (template: templates/ADR/)"
	@echo "    3. make prepare-and-publish   (AI prep + publish HLD)"
	@echo "    4. make build-lld             (publish LLD)"
	@echo "    5. make workitems"
	@echo ""
	@echo "  Overwrite / re-extract (GNU make does not accept --force):"
	@echo "    make setup CLIENT=\"Example Client\" FORCE=1"
	@echo "    make build-hld-from-adr FORCE=1"
	@echo "    make build-hld-from-adr force"
	@echo ""
	@echo "  Note: 'make publish' writes local output/ (gitignored). It does not git push"
	@echo "  or push a container image. Use 'make push' to push the image to a registry."
	@echo ""

# ── Container image ──────────────────────────────────────────────────

image: ## Build the container image (auto-built on first use, rebuilds if scripts/Containerfile changed)
	@image_hash="$$($(ENGINE) image inspect $(IMAGE) --format '{{ index .Config.Labels "org.opencontainers.image.scripts-hash" }}' 2>/dev/null || true)"; \
	if [ -z "$$image_hash" ]; then \
		echo "Building container image '$(IMAGE)'..."; \
		$(ENGINE) build --build-arg SCRIPTS_HASH=$(_SCRIPTS_HASH) -t $(IMAGE) .; \
	elif [ "$$image_hash" != "$(_SCRIPTS_HASH)" ]; then \
		echo "Image '$(IMAGE)' is stale (Containerfile or scripts/ changed since last build) — rebuilding..."; \
		$(ENGINE) build --build-arg SCRIPTS_HASH=$(_SCRIPTS_HASH) -t $(IMAGE) .; \
	else \
		echo "Image '$(IMAGE)' is up to date."; \
	fi

force-image: ## Force rebuild the container image
	@echo "Rebuilding container image '$(IMAGE)'..."
	@$(ENGINE) build --build-arg SCRIPTS_HASH=$(_SCRIPTS_HASH) -t $(IMAGE) .

# ── Project setup ────────────────────────────────────────────────────

setup: image ## First-time project setup — provide CLIENT="Your Client Name" (optional PROJECT="OCP-V" FORCE=1)
	@if [ -z "$(CLIENT)" ]; then \
		echo ""; \
		echo "  Usage: make setup CLIENT=\"Your Client Name\" PROJECT=\"OCP-V\" [FORCE=1]"; \
		echo ""; \
		exit 1; \
	fi
	@force_arg=""; \
	if [ -n "$(_FORCE_ON)" ]; then force_arg="--force"; fi; \
	$(_RUN) setup "$(CLIENT)" "$(PROJECT)" $$force_arg

status: ## Check what's configured, what's built, what's missing
	@$(PYTHON) scripts/setup_project.py . --status

# ── Container build targets ──────────────────────────────────────────

build: prepare-hld-ai image ## Full pipeline: AI draft + HLD + LLD + work items → output/
	@mkdir -p output
	@$(_RUNOUT) build all

rebuild: clean-build clean-ai build ## Clean build output + AI state, then full rebuild

publish: image ## Stitch HLD, export diagrams, generate PDFs → output/ (container only)
	@mkdir -p output
	@$(_RUNOUT) build hld

build-hld: publish

build-hld-from-adr: prepare-hld-ai ## AI prepare HLD inputs from ADR (host only)

prepare-and-publish: build-hld-from-adr publish ## Run AI prep, then publish HLD artifacts

build-lld: image ## Stitch LLD phases, export diagrams, generate PDFs → output/
	@mkdir -p output
	@$(_RUNOUT) build lld

diagrams: image ## Export all diagrams (.drawio + mermaid) to PNG → output/
	@mkdir -p output
	@$(_RUNOUT) diagrams

pdfs: image ## Regenerate PDFs only (skip diagram export) → output/
	@mkdir -p output
	@$(_RUNOUT) pdfs

workitems: image ## Create sprint work items from LLD → output/Work_Items/
	@mkdir -p output
	@$(_RUNOUT) workitems

rvtools: image ## Process RVTools XLSX into migration schedule (default: RVTools/*.xlsx)
	@mkdir -p output
	@$(_RUNOUT) rvtools $(or $(FILES),RVTools/*.xlsx)

push: ## Push container image to registry (set IMAGE= and REGISTRY=)
	@if [ -z "$(REGISTRY)" ]; then \
		echo "Usage: make push REGISTRY=quay.io/your-org"; \
		exit 1; \
	fi
	@$(ENGINE) tag $(IMAGE) $(REGISTRY)/$(IMAGE)
	@$(ENGINE) push $(REGISTRY)/$(IMAGE)
	@echo "Pushed to $(REGISTRY)/$(IMAGE)"

# ── Host AI targets ──────────────────────────────────────────────────
# Variables:
#   PHASE           phase1 | phase2 | phase3 | phase4
#   FORCE           1  (re-extract slots even when inputs are unchanged; also: make <target> force)
#   RUNS            number of repeatability test runs (default: 3)
#   AI_TOOL         claude | codex | cursor (default: cursor)
#   AI_MODEL        model name (default: claude-sonnet-4-6)
#   AI_TIMEOUT      per-call timeout seconds (default: 900; single-pass Prompt A)
#   AI_MAX_CHARS    max chars per ADR chunk in chunked mode (default: 12000)
#   AI_MAX_CHUNKS   max ADR chunks in chunked mode (default: 8)
#   ADR_MODE        auto | chunked (default: auto = full ADR then 8x12k fallback)
#   REFINE_PHASES   1  (opt in to Prompt B per-phase refine; off by default)
#   CANONICAL_DIR   optional path to canonical files for benchmark mode

prepare-hld-ai: ## AI extract/render/write-back for HLD inputs (host only)
	@mkdir -p "$(OUTPUT_ROOT)"
	@OUTPUT_ROOT="$(OUTPUT_ROOT)" $(PYTHON) scripts/hld_lld/ai/ai_draft_deterministic.py hld --extractor ai \
		$(if $(PHASE),--phase $(PHASE)) \
		$(if $(_FORCE_ON),--force) \
		$(if $(AI_TOOL),--ai-tool $(AI_TOOL)) \
		$(if $(AI_MODEL),--ai-model $(AI_MODEL)) \
		$(if $(AI_MAX_CHARS),--ai-max-chars $(AI_MAX_CHARS)) \
		$(if $(AI_MAX_CHUNKS),--ai-max-chunks $(AI_MAX_CHUNKS)) \
		$(if $(AI_PHASE_MAX_CHARS),--ai-phase-max-chars $(AI_PHASE_MAX_CHARS)) \
		$(if $(AI_RETRIES),--ai-retries $(AI_RETRIES)) \
		$(if $(AI_TIMEOUT),--ai-timeout $(AI_TIMEOUT)) \
		$(if $(ADR_MODE),--adr-mode $(ADR_MODE)) \
		$(if $(REFINE_PHASES),--refine-phases) \
		$(if $(CANONICAL_DIR),--canonical-dir $(CANONICAL_DIR))

draft-hld-ai-normalize: prepare-hld-ai

validate-hld-ai-normalize: ## Validate AI-normalized HLD outputs
	@mkdir -p "$(OUTPUT_ROOT)"
	@OUTPUT_ROOT="$(OUTPUT_ROOT)" $(PYTHON) scripts/hld_lld/ai/ai_draft_deterministic.py hld --extractor ai --validate-only \
		$(if $(PHASE),--phase $(PHASE)) \
		$(if $(CANONICAL_DIR),--canonical-dir $(CANONICAL_DIR))

test-hld-ai-repeatability: ## Run AI extraction+render N times and compare hashes (RUNS=3)
	@$(PYTHON) scripts/hld_lld/ai/deterministic/cli.py test-repeatability \
		--project-root . \
		$(if $(PHASE),--phase $(PHASE)) \
		$(if $(RUNS),--runs $(RUNS)) \
		$(if $(AI_TOOL),--ai-tool $(AI_TOOL)) \
		$(if $(AI_MODEL),--ai-model $(AI_MODEL)) \
		$(if $(CANONICAL_DIR),--canonical-dir $(CANONICAL_DIR))

inspect-slots: ## Show extracted slot values (run after prepare-hld-ai)
	@$(PYTHON) scripts/hld_lld/ai/deterministic/cli.py inspect-slots --slots "$(OUTPUT_ROOT)/.deterministic/slots/slot_map.json"

inspect-chunks: ## Show how ADR files will be split into AI prompt chunks
	@$(PYTHON) scripts/hld_lld/ai/deterministic/cli.py inspect-chunks \
		--adr-dir ADR \
		$(if $(AI_MAX_CHARS),--max-chars $(AI_MAX_CHARS)) \
		$(if $(AI_MAX_CHUNKS),--max-chunks $(AI_MAX_CHUNKS))

validate-slots: ## Validate extracted slot JSON against schema
	@$(PYTHON) scripts/hld_lld/ai/deterministic/cli.py validate-slots \
		--slots "$(OUTPUT_ROOT)/.deterministic/slots/slot_map.json" \
		--phases phase1 phase2 phase3 phase4

combine-drawio: ## Combine .drawio files by prefix group
	@$(PYTHON) scripts/shared/tools/combine_drawio.py "$(OUTPUT_ROOT)/Diagrams"

sanitize-diagrams: ## Sanitize client-specific drawio examples
	@$(PYTHON) scripts/shared/tools/sanitize_diagrams.py

sample-schedule: ## Generate sample migration schedule workbook
	@mkdir -p "$(OUTPUT_ROOT)"
	@$(PYTHON) scripts/rvtools/generate_sample_schedule.py -o "$(OUTPUT_ROOT)/Sample_Migration_Weekly_Schedule.xlsx"


check-annotations: ## Check HLD source files for drawio annotations (host only, no container)
	@$(PYTHON) scripts/hld_lld/build/check_annotations.py

lld-closeness: ## Compare rendered LLD vs canonical fixture (CANONICAL=/path/to/LLD)
	@if [ -z "$(CANONICAL)" ]; then \
		echo "Usage: make lld-closeness CANONICAL=/path/to/canonical/LLD"; \
		exit 1; \
	fi
	@$(PYTHON) scripts/hld_lld/report_lld_closeness.py --canonical-dir "$(CANONICAL)"

package: ## Zip up only what's needed to run make targets on a fresh host (set PACKAGE_OUTPUT=path/to.zip)
	@bash scripts/shared/tools/package_release.sh $(if $(PACKAGE_OUTPUT),"$(PACKAGE_OUTPUT)")

# ── Health Check (host only, no container) ───────────────────────────
HC_COLLECT_OUT ?= output/hc_collect
# HC_SSH_HOST:    user@hostname of the support shell server (required)
# HC_SSH_RESULTS: path to hc_results on remote   (default ~/hc_results)
# HC_SSH_SCRIPTS: path to deploy scripts on remote (default ~/hc_supportshell)
# HC_MG_INPUT:    must-gather or case dir on remote, for hc-collect-remote
HC_SSH_HOST    ?=
HC_SSH_RESULTS ?= ~/hc_results
HC_SSH_SCRIPTS ?= ~/hc_supportshell
HC_MG_INPUT    ?=
HC_FETCH_DATE  := $(shell date +%F)
HC_FETCH_STAGE := $(HC_COLLECT_OUT)/$(HC_FETCH_DATE)

hc-collect: ## Collect cluster data against live cluster — runs on host (set KUBECONFIG=)
	@bash scripts/health_check/collect/hc_collect.sh \
		$(if $(KUBECONFIG),--kubeconfig "$(KUBECONFIG)") \
		--output-dir "$(HC_COLLECT_OUT)"

hc-push-scripts: ## Push supportshell collection scripts to remote server (set HC_SSH_HOST=user@host)
	$(call require,HC_SSH_HOST,Error: set HC_SSH_HOST=user@host)
	$(call warn_missing_project_yaml)
	@echo "Pushing scripts → $(HC_SSH_HOST):$(HC_SSH_SCRIPTS)/"
	@ssh "$(HC_SSH_HOST)" "mkdir -p $(HC_SSH_SCRIPTS)"
	@rsync -av --delete scripts/health_check/supportshell/ "$(HC_SSH_HOST):$(HC_SSH_SCRIPTS)/"
	@echo "Done. Scripts are at $(HC_SSH_SCRIPTS)/ on the remote server."
	@echo ""
	@echo "Next steps (manual — 'yank' is an interactive tool and cannot be automated):"
	@echo "  1. ssh $(HC_SSH_HOST)"
	@echo "  2. yank <case-number>   (extracts the support case / must-gather bundle)"
	@echo "  3. Then from your workstation:"
	@echo "       make hc-collect-remote HC_SSH_HOST=$(HC_SSH_HOST) HC_MG_INPUT=<absolute-path-from-yank>"

hc-collect-remote: ## Run supportshell collection on the remote server via SSH (set HC_SSH_HOST=user@host HC_MG_INPUT=<case-or-must-gather-path>)
	$(call require,HC_SSH_HOST,Error: set HC_SSH_HOST=user@host)
	$(call require,HC_MG_INPUT,Error: set HC_MG_INPUT=<must-gather-path-on-remote> — run 'yank <case>' on the server first)
	$(call warn_missing_project_yaml)
	@ssh -t "$(HC_SSH_HOST)" "if [ ! -e $(HC_MG_INPUT) ]; then echo \"[ERROR] HC_MG_INPUT not found: $(HC_MG_INPUT)\" >&2; echo \"Hint: run 'yank <case-number>' on the remote host, then pass the exact extracted path.\" >&2; echo \"Example: make hc-collect-remote HC_SSH_HOST=$(HC_SSH_HOST) HC_MG_INPUT=<absolute-path-from-yank>\" >&2; exit 1; fi; bash $(HC_SSH_SCRIPTS)/hc_collect_multi.sh --input $(HC_MG_INPUT) --output-dir $(HC_SSH_RESULTS) --tar"
	@echo "Done. Run 'make hc-fetch-results HC_SSH_HOST=$(HC_SSH_HOST)' to copy results."

hc-fetch-results: ## Fetch hc_results from remote support shell server — tarball preferred, raw dir fallback (set HC_SSH_HOST=user@host)
	$(call require,HC_SSH_HOST,Error: set HC_SSH_HOST=user@host)
	@bash scripts/health_check/hc_fetch_results.sh \
		--ssh-host "$(HC_SSH_HOST)" \
		--remote-results "$(HC_SSH_RESULTS)" \
		--staging-dir "$(HC_FETCH_STAGE)"
	@echo "Done. Results staged at $(HC_FETCH_STAGE)."

hc-merge: ## Merge multiple hc_results dirs on the host (set MERGE_INPUTS="dir1 dir2")
	$(call require,MERGE_INPUTS,Error: set MERGE_INPUTS=\"dir1 dir2 ...\")
	@$(PYTHON) scripts/health_check/supportshell/hc_merge.py $(MERGE_INPUTS) -o "$(HC_COLLECT_OUT)"
	@echo "Merged results → $(HC_COLLECT_OUT)"

clean-hc: ## Remove health check pipeline output
	@echo "Cleaning health check output..."
	@rm -rf output/hc_collect output/Health_Check_Report
	@echo "Done."

# ── Housekeeping ─────────────────────────────────────────────────────

clean: clean-build clean-ai clean-setup ## Reset to fresh-clone state (removes all generated files)

clean-build: ## Remove all build output (output/)
	@echo "Cleaning output/..."
	@rm -rf output
	@echo "Done."

clean-hld: ## Remove HLD build output only
	@echo "Cleaning HLD output..."
	@rm -rf output/HLD
	@echo "Done."

clean-lld: ## Remove LLD build output only
	@echo "Cleaning LLD output..."
	@rm -rf output/LLD
	@echo "Done."

clean-pdfs: ## Remove generated PDFs only (HLD + LLD)
	@echo "Cleaning PDFs..."
	@rm -rf output/HLD/PDFs output/LLD/PDFs
	@echo "Done."

clean-diagrams: ## Remove exported diagram PNGs only
	@echo "Cleaning diagrams..."
	@rm -rf output/Diagrams output/HLD/diagrams output/LLD/diagrams
	@echo "Done."

clean-workitems: ## Remove generated work items only
	@echo "Cleaning work items..."
	@rm -rf output/Work_Items
	@echo "Done."

clean-ai: ## Remove AI drafts and deterministic state only
	@echo "Cleaning AI drafts and state..."
	@rm -rf drafts drafts_deterministic .deterministic .cursor-sdk-venv venv "$(OUTPUT_ROOT)/drafts_deterministic" "$(OUTPUT_ROOT)/.deterministic"
	@echo "Done."

clean-setup: ## Remove setup artifacts (project.yaml, client files, work items, scaffolded dirs)
	@echo "Cleaning setup artifacts..."
	@# Client working copies under output/ (templates/ is immutable)
	@rm -rf output/HLD/markdown_files output/LLD
	@rm -rf output/Diagrams/phase1 output/Diagrams/phase2 output/Diagrams/phase3 output/Diagrams/phase4
	@find output/Diagrams -maxdepth 1 -name '*.drawio' -delete 2>/dev/null || true
	@rm -rf output/Work_Items output/HLD/PDFs output/HLD/diagrams output/HLD/READOUT output/LLD/PDFs output/LLD/diagrams
	@# Client ADR files at repo root (templates live under templates/ADR/)
	@find ADR -maxdepth 1 -name 'ADR_*.md' ! -name 'ADR_template.md' ! -name 'ADR_EXAMPLE.md' -delete 2>/dev/null || true
	@rm -rf RVTools
	@# Project config
	@rm -f project.yaml
	@echo "Done."
