VERSION := 0.1.5
NAME := metadata.csfd
BUILD_DIR := build

.PHONY: test zip clean
test:
	pytest

zip:
	mkdir -p $(BUILD_DIR)
	rm -f $(BUILD_DIR)/$(NAME)-$(VERSION).zip
	git archive --format=zip --prefix=$(NAME)/ -o $(BUILD_DIR)/$(NAME)-$(VERSION).zip HEAD

clean:
	rm -f $(BUILD_DIR)/$(NAME)-$(VERSION).zip

# Kodi expects the addon id (metadata.csfd) as the top folder inside the
# zip, even though this working dir is named csfd-meta. `git archive` roots
# the archive under the --prefix regardless of the working dir name, and
# .gitattributes export-ignore entries strip non-addon files (tests/, docs/,
# etc.). Note: git archive packages COMMITTED files only, so `make zip` must
# be run after committing.
