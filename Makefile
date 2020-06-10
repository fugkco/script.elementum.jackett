NAME = script.elementum.jackett
GIT = git
LAST_GIT_TAG = $(shell $(GIT) describe --tags)
GIT_VERSION = $(shell $(GIT) describe --abbrev=0 --tags --exact-match 2>/dev/null || echo -n "$(LAST_GIT_TAG)-snapshot")
ZIP_SUFFIX = zip
ZIP_FILE = $(NAME).$(ZIP_SUFFIX)

BUILD_DIR = build/$(NAME)

all: clean deps-prod locales zip

.PHONY: build-prod
build-prod: clean deps-prod $(ZIP_FILE)

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
			--progress-bar off \
			--install-option="--install-scripts=$$(mktemp -d)"
	@find $(BUILD_DIR) -iname "*.egg-info" -or -iname "*.pyo" -or -iname "*.pyc" | xargs rm -rf
	@poetry run ./scripts/update-version.py $(GIT_VERSION) > $(BUILD_DIR)/addon.xml

.PHONY: zip
zip: $(ZIP_FILE)

clean:
	rm -f $(ZIP_FILE)

locales:
	scripts/xgettext_merge.sh
