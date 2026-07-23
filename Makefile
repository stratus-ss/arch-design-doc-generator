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
#   2. Fill in ADR/<client>.md           # record architecture decisions
#   3. make build                        # AI draft + stitch + diagrams + PDFs + work items

# ── Container engine ─────────────────────────────────────────────────
# Detects podman first, falls back to docker.  Override: make build ENGINE=docker
ENGINE ?= $(shell command -v podman 2>/dev/null || echo docker)
IMAGE  ?= arch-doc-gen

_RUN    := $(ENGINE) run --rm -v "$$(pwd)":/workspace:Z --entrypoint /workspace/scripts/entrypoint.sh $(IMAGE)
_RUNOUT := $(ENGINE) run --rm -v "$$(pwd)":/workspace:Z -v "$$(pwd)/output":/output:Z --entrypoint /workspace/scripts/entrypoint.sh $(IMAGE)

# ── Python interpreter ───────────────────────────────────────────────
PYTHON ?= python3
OUTPUT_ROOT ?= output
PROJECT ?= OCP-V

# ── Makefile config ──────────────────────────────────────────────────
.DEFAULT_GOAL := help

.PHONY: help \
        image setup build rebuild publish prepare-and-publish build-hld build-hld-from-adr build-lld \
        diagrams pdfs workitems rvtools status \
        prepare-hld-ai draft-hld-ai-normalize validate-hld-ai-normalize \
        test-hld-ai-repeatability \
        inspect-slots inspect-chunks validate-slots \
        combine-drawio sanitize-diagrams sample-schedule \
        clean clean-build clean-hld clean-lld clean-pdfs clean-diagrams clean-workitems clean-ai clean-setup push

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
	echo ""; \
	echo "  Maintenance:"; \
	print_target image; \
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
	@echo "    2. Fill in ADR/<client>.md"
	@echo "    3. make prepare-and-publish   (AI prep + publish HLD)"
	@echo "    4. make build-lld             (publish LLD)"
	@echo "    5. make workitems"
	@echo ""

# ── Container image ──────────────────────────────────────────────────

image: Containerfile ## Build the container image (auto-built on first use)
	@if ! $(ENGINE) image exists $(IMAGE) 2>/dev/null; then \
		echo "Building container image '$(IMAGE)'..."; \
		$(ENGINE) build -t $(IMAGE) .; \
	else \
		echo "Image '$(IMAGE)' already exists. Rebuild: $(ENGINE) build -t $(IMAGE) ."; \
	fi

# ── Project setup ────────────────────────────────────────────────────

setup: image ## First-time project setup — provide CLIENT="Your Client Name" (optional PROJECT="OCP-V")
	@if [ -z "$(CLIENT)" ]; then \
		echo ""; \
		echo "  Usage: make setup CLIENT=\"Your Client Name\" PROJECT=\"OCP-V\""; \
		echo ""; \
		exit 1; \
	fi
	@$(_RUN) setup "$(CLIENT)" "$(PROJECT)"

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
#   FORCE           1  (overwrite existing drafts)
#   RUNS            number of repeatability test runs (default: 3)
#   AI_TOOL         claude | codex | cursor (default: cursor)
#   AI_MODEL        model name (default: claude-sonnet-4-6)
#   AI_MAX_CHARS    max chars per ADR chunk (default: 12000)
#   AI_MAX_CHUNKS   max ADR chunks for Prompt A (default: 8)
#   CANONICAL_DIR   optional path to canonical files for benchmark mode

prepare-hld-ai: ## AI extract/render/write-back for HLD inputs (host only)
	@mkdir -p $(OUTPUT_ROOT)
	@OUTPUT_ROOT="$(OUTPUT_ROOT)" $(PYTHON) scripts/ai/ai_draft_deterministic.py hld --extractor ai \
		$(if $(PHASE),--phase $(PHASE)) \
		$(if $(FORCE),--force) \
		$(if $(AI_TOOL),--ai-tool $(AI_TOOL)) \
		$(if $(AI_MODEL),--ai-model $(AI_MODEL)) \
		$(if $(AI_MAX_CHARS),--ai-max-chars $(AI_MAX_CHARS)) \
		$(if $(AI_MAX_CHUNKS),--ai-max-chunks $(AI_MAX_CHUNKS)) \
		$(if $(AI_PHASE_MAX_CHARS),--ai-phase-max-chars $(AI_PHASE_MAX_CHARS)) \
		$(if $(AI_RETRIES),--ai-retries $(AI_RETRIES)) \
		$(if $(AI_TIMEOUT),--ai-timeout $(AI_TIMEOUT)) \
		$(if $(SKIP_PHASE_REFINE),--skip-phase-refine) \
		$(if $(CANONICAL_DIR),--canonical-dir $(CANONICAL_DIR))

draft-hld-ai-normalize: prepare-hld-ai

validate-hld-ai-normalize: ## Validate AI-normalized HLD outputs
	@mkdir -p $(OUTPUT_ROOT)
	@OUTPUT_ROOT="$(OUTPUT_ROOT)" $(PYTHON) scripts/ai/ai_draft_deterministic.py hld --extractor ai --validate-only \
		$(if $(PHASE),--phase $(PHASE)) \
		$(if $(CANONICAL_DIR),--canonical-dir $(CANONICAL_DIR))

test-hld-ai-repeatability: ## Run AI extraction+render N times and compare hashes (RUNS=3)
	@$(PYTHON) scripts/ai/deterministic/cli.py test-repeatability \
		--project-root . \
		$(if $(PHASE),--phase $(PHASE)) \
		$(if $(RUNS),--runs $(RUNS)) \
		$(if $(AI_TOOL),--ai-tool $(AI_TOOL)) \
		$(if $(AI_MODEL),--ai-model $(AI_MODEL)) \
		$(if $(CANONICAL_DIR),--canonical-dir $(CANONICAL_DIR))

inspect-slots: ## Show extracted slot values (run after prepare-hld-ai)
	@$(PYTHON) scripts/ai/deterministic/cli.py inspect-slots --slots "$(OUTPUT_ROOT)/.deterministic/slots/slot_map.json"

inspect-chunks: ## Show how ADR files will be split into AI prompt chunks
	@$(PYTHON) scripts/ai/deterministic/cli.py inspect-chunks \
		--adr-dir ADR \
		$(if $(AI_MAX_CHARS),--max-chars $(AI_MAX_CHARS)) \
		$(if $(AI_MAX_CHUNKS),--max-chunks $(AI_MAX_CHUNKS))

validate-slots: ## Validate extracted slot JSON against schema
	@$(PYTHON) scripts/ai/deterministic/cli.py validate-slots \
		--slots "$(OUTPUT_ROOT)/.deterministic/slots/slot_map.json" \
		--phases phase1 phase2 phase3 phase4

combine-drawio: ## Combine .drawio files by prefix group
	@$(PYTHON) scripts/tools/combine_drawio.py Diagrams

sanitize-diagrams: ## Sanitize client-specific drawio examples
	@$(PYTHON) scripts/tools/sanitize_diagrams.py

sample-schedule: ## Generate sample migration schedule workbook
	@mkdir -p "$(OUTPUT_ROOT)"
	@$(PYTHON) scripts/tools/generate_sample_schedule.py -o "$(OUTPUT_ROOT)/Sample_Migration_Weekly_Schedule.xlsx"

# ── Housekeeping ─────────────────────────────────────────────────────

clean: clean-build clean-ai clean-setup ## Reset to fresh-clone state (removes all generated files)

clean-build: ## Remove all build output (output/)
	@echo "Cleaning output/..."
	@rm -rf output
	@echo "Done."

clean-hld: ## Remove HLD build output only
	@echo "Cleaning HLD output..."
	@rm -rf output/HLD
	@rm -f HLD/markdown_files/*_combined.md HLD/markdown_files/Drawio_*.md
	@rm -rf HLD/PDFs HLD/diagrams
	@echo "Done."

clean-lld: ## Remove LLD build output only
	@echo "Cleaning LLD output..."
	@rm -rf output/LLD
	@rm -f LLD/*_Combined.md LLD/Drawio_*.md
	@rm -rf LLD/PDFs LLD/diagrams
	@echo "Done."

clean-pdfs: ## Remove generated PDFs only (HLD + LLD)
	@echo "Cleaning PDFs..."
	@rm -rf output/HLD/PDFs output/LLD/PDFs HLD/PDFs LLD/PDFs
	@echo "Done."

clean-diagrams: ## Remove exported diagram PNGs only
	@echo "Cleaning diagrams..."
	@rm -rf output/Diagrams output/HLD/diagrams output/LLD/diagrams
	@rm -rf HLD/diagrams LLD/diagrams
	@find Diagrams -name "*.png" -delete 2>/dev/null || true
	@echo "Done."

clean-workitems: ## Remove generated work items only
	@echo "Cleaning work items..."
	@rm -rf output/Work_Items Work_Items
	@echo "Done."

clean-ai: ## Remove AI drafts and deterministic state only
	@echo "Cleaning AI drafts and state..."
	@rm -rf drafts drafts_deterministic .deterministic .cursor-sdk-venv venv "$(OUTPUT_ROOT)/drafts_deterministic" "$(OUTPUT_ROOT)/.deterministic"
	@echo "Done."

clean-setup: ## Remove setup artifacts (project.yaml, client files, work items, scaffolded dirs)
	@echo "Cleaning setup artifacts..."
	@# Client-named files: anything not starting with "Template_" in HLD/markdown_files
	@find HLD/markdown_files -maxdepth 1 -name '*.md' ! -name 'Template_*' -delete 2>/dev/null || true
	@# Combined template docs are regenerated by stitch, remove them too
	@rm -f HLD/markdown_files/Template_*_combined.md
	@rm -f HLD/markdown_files/*_combined_deterministic.md HLD/markdown_files/Drawio_*.md
	@# Client LLD files (not templates)
	@find LLD -maxdepth 1 -name '*.md' ! -name 'Template_*' -delete 2>/dev/null || true
	@rm -f LLD/Drawio_*.md
	@# Client ADR files (not the template)
	@find ADR -maxdepth 1 -name 'ADR_*.md' ! -name 'ADR_template.md' -delete 2>/dev/null || true
	@# Scaffolded / generated directories
	@rm -rf Work_Items HLD/PDFs HLD/diagrams HLD/READOUT LLD/PDFs LLD/diagrams RVTools
	@rm -rf Diagrams/phase1 Diagrams/phase2 Diagrams/phase3 Diagrams/phase4
	@rm -rf Diagrams/tools
	@find Diagrams -maxdepth 1 -name '*.drawio' -not -path 'Diagrams/examples/*' -delete 2>/dev/null || true
	@# Project config
	@rm -f project.yaml
	@echo "Done."
