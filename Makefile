NAME = script.elementum.jackett
GIT = git
LAST_GIT_TAG = $(shell $(GIT) describe --tags)
GIT_VERSION = $(shell $(GIT) describe --abbrev=0 --tags --exact-match 2>/dev/null || echo -n "$(LAST_GIT_TAG)-snapshot")

ZIP = zip
ZIP_SUFFIX = zip
ZIP_FILE = $(NAME).$(ZIP_SUFFIX)

BUILD_BASE = build
BUILD_DIR = $(BUILD_BASE)/$(NAME)

all: clean deps-prod locales zip

.PHONY: build-prod
build-prod: clean deps-prod $(ZIP_FILE)

.PHONY: deps-prod
deps-prod: clean deps-prod $(ZIP_FILE)
	@poetry install --no-dev

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

deps-dev:
	@poetry install

$(ZIP_FILE): $(BUILD_DIR)
	$(GIT) archive --format tar --worktree-attributes HEAD | tar -xvf - -C $(BUILD_DIR)
	@poetry export -f requirements.txt | \
		poetry run pip install \
			--requirement /dev/stdin \
			--target $(BUILD_DIR)/resources/libs \
			--progress-bar off
	@find $(BUILD_DIR) -iname "*.egg-info" -or -iname "*.pyo" -or -iname "*.pyc" | xargs rm -rf
	@poetry run ./scripts/update-version.py $(GIT_VERSION) > $(BUILD_DIR)/addon.xml
	@(cd $(BUILD_BASE) && $(ZIP) -r $(CURDIR)/$(ZIP_FILE) $(NAME))

.PHONY: zip
zip: $(ZIP_FILE)

clean:
	rm -f $(ZIP_FILE)
	rm -rf $(BUILD_DIR)

locales:
	scripts/xgettext_merge.sh
