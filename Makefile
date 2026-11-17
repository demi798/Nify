# Nify 项目管理
ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND_DIR := $(ROOT_DIR)/backend
FRONTEND_DIR := $(ROOT_DIR)/frontend
DIST_DIR := $(ROOT_DIR)/dist
PACKAGE_NAME := nify
PACKAGE_VERSION ?= 0.1.0
PACKAGE_FILE := $(DIST_DIR)/$(PACKAGE_NAME)-$(PACKAGE_VERSION).tar.gz
STAGING_DIR := $(DIST_DIR)/staging/$(PACKAGE_NAME)-$(PACKAGE_VERSION)

.PHONY: start stop restart build build-backend build-frontend clean package help

help:
	@echo "Nify Makefile targets:"
	@echo "  make start     - 检查依赖并启动后端 + 前端"
	@echo "  make stop      - 优雅停止后端 + 前端"
	@echo "  make restart   - 先 stop 再 start"
	@echo "  make build     - 构建后端依赖 + 前端生产包"
	@echo "  make clean     - 清理构建产物与临时文件"
	@echo "  make package   - 打包可分发归档到 dist/"

start:
	@chmod +x "$(ROOT_DIR)/start.sh"
	@"$(ROOT_DIR)/start.sh"

stop:
	@chmod +x "$(ROOT_DIR)/stop.sh"
	@"$(ROOT_DIR)/stop.sh"

restart:
	@$(MAKE) stop
	@$(MAKE) start

build: build-backend build-frontend
	@echo "[信息] 前后端构建完成"

build-backend:
	@echo "[信息] 安装后端依赖…"
	@cd "$(BACKEND_DIR)" && \
		if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi && \
		python3 -m pip install -e ".[dev]"

build-frontend:
	@echo "[信息] 构建前端…"
	@cd "$(FRONTEND_DIR)" && \
		if [ ! -d node_modules ]; then npm install; fi && \
		npm run build

clean:
	@echo "[信息] 清理构建产物…"
	@rm -rf "$(FRONTEND_DIR)/dist"
	@rm -rf "$(FRONTEND_DIR)/node_modules/.vite"
	@find "$(BACKEND_DIR)" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	@find "$(BACKEND_DIR)" -type d -name "*.egg-info" -prune -exec rm -rf {} + 2>/dev/null || true
	@find "$(BACKEND_DIR)" -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	@find "$(BACKEND_DIR)" -type d -name ".mypy_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	@find "$(BACKEND_DIR)" -type d -name ".ruff_cache" -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -f "$(BACKEND_DIR)/log/nify-backend.log" "$(BACKEND_DIR)/log/nify-frontend.log"
	@rm -f "$(BACKEND_DIR)/log/nify-frontend-install.log"
	@rm -f "$(ROOT_DIR)/.nify-backend.pid" "$(ROOT_DIR)/.nify-frontend.pid"
	@rm -rf "$(DIST_DIR)"
	@echo "[信息] 清理完成（未删除 node_modules / .venv）"

package: build
	@echo "[信息] 打包 $(PACKAGE_FILE)…"
	@rm -rf "$(DIST_DIR)/staging"
	@mkdir -p "$(STAGING_DIR)"
	@cp "$(ROOT_DIR)/CLAUDE.md" "$(ROOT_DIR)/Makefile" "$(ROOT_DIR)/start.sh" "$(ROOT_DIR)/stop.sh" "$(STAGING_DIR)/"
	@chmod +x "$(STAGING_DIR)/start.sh" "$(STAGING_DIR)/stop.sh"
	@rsync -a \
		--exclude '.venv' \
		--exclude '__pycache__' \
		--exclude '*.pyc' \
		--exclude '*.egg-info' \
		--exclude '.pytest_cache' \
		--exclude '.mypy_cache' \
		--exclude '.ruff_cache' \
		--exclude '.env' \
		"$(BACKEND_DIR)/" "$(STAGING_DIR)/backend/"
	@rsync -a \
		--exclude 'node_modules' \
		--exclude '.vite' \
		--exclude '.env' \
		"$(FRONTEND_DIR)/" "$(STAGING_DIR)/frontend/"
	@mkdir -p "$(DIST_DIR)"
	@tar -czf "$(PACKAGE_FILE)" -C "$(DIST_DIR)/staging" "$(PACKAGE_NAME)-$(PACKAGE_VERSION)"
	@rm -rf "$(DIST_DIR)/staging"
	@echo "[信息] 已生成: $(PACKAGE_FILE)"
