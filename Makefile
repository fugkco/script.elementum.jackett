NAME = script.elementum.jackett
GIT = git
GIT_VERSION = $(shell $(GIT) describe --abbrev=0 --tags 2>/dev/null || echo -n "v0.0.1-snapshot")
GIT_USER = fugkco
GIT_REPOSITORY = script.elementum.jackett
VERSION = $(shell sed -ne "s/.*COLOR\]\"\sversion=\"\([0-9a-z\.\-]*\)\".*/\1/p" addon.xml)
ZIP_SUFFIX = zip
ZIP_FILE = $(NAME).$(ZIP_SUFFIX)

all: clean deps-prod locales zip

.PHONY: build-prod
build-prod: clean deps-prod $(ZIP_FILE)

deps-prod:
	@poetry export -f requirements.txt | \
		poetry run pip install \
			--requirement /dev/stdin \
			--target $(NAME)/resources/libs \
			--progress-bar off \
			--install-option="--install-scripts=$$(mktemp -d)"

deps-dev:
	@poetry install

$(ZIP_FILE): deps-prod
	$(GIT) archive --format zip --worktree-attributes --prefix $(NAME)/ --output $(ZIP_FILE) HEAD
	@zip -u -r $(ZIP_FILE) $(NAME)/resources/libs -x "*.pyc" -x "*.pyo" -x "**/*.egg-info/*"
	rm -rf $(NAME)

zip: $(ZIP_FILE)

clean:
	rm -f $(ZIP_FILE)

locales:
	scripts/xgettext_merge.sh
