VERSION := 0.1.0
NAME := metadata.csfd

.PHONY: test zip clean
test:
	pytest

zip:
	rm -f $(NAME)-$(VERSION).zip
	git archive --format=zip --prefix=$(NAME)/ -o $(NAME)-$(VERSION).zip HEAD

clean:
	rm -f $(NAME)-$(VERSION).zip

# Kodi expects the addon id (metadata.csfd) as the top folder inside the
# zip, even though this working dir is named csfd-meta. `git archive` roots
# the archive under the --prefix regardless of the working dir name, and
# .gitattributes export-ignore entries strip non-addon files (tests/, docs/,
# etc.). Note: git archive packages COMMITTED files only, so `make zip` must
# be run after committing.
