NAME = script.elementum.jackett
GIT = git
GIT_VERSION = $(shell $(GIT) describe --abbrev=0 --tags 2>/dev/null || echo -n "v0.0.1-snapshot")
GIT_USER = fugkco
GIT_REPOSITORY = script.elementum.jackett
VERSION = $(shell sed -ne "s/.*COLOR\]\"\sversion=\"\([0-9a-z\.\-]*\)\".*/\1/p" addon.xml)
ZIP_SUFFIX = zip
ZIP_FILE = $(NAME)-$(VERSION).$(ZIP_SUFFIX)

all: deps-prod clean zip

deps-prod:
	@pipenv --rm || true
	@pipenv install
	@pipenv run pip freeze | pipenv run pip install --upgrade -r /dev/stdin --target resources/libs

deps-dev:
	@pipenv --rm
	@pipenv install --dev

$(ZIP_FILE):
	$(GIT) archive --format zip --prefix $(NAME)/ --output $(ZIP_FILE) HEAD
	rm -rf $(NAME)

zip: $(ZIP_FILE)

clean_arch:
	 rm -f $(ZIP_FILE)

clean:
	rm -f $(ZIP_FILE)
	rm -rf $(NAME)

locales:
	scripts/xgettext_merge.sh
