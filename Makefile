VERSION := 0.1.0
NAME := metadata.csfd

.PHONY: test zip clean
test:
	pytest

zip:
	rm -f $(NAME)-$(VERSION).zip
	cd .. && zip -r csfd-meta/$(NAME)-$(VERSION).zip csfd-meta \
		-x 'csfd-meta/.git/*' 'csfd-meta/tests/*' 'csfd-meta/.idea/*' \
		'csfd-meta/docs/*' 'csfd-meta/.superpowers/*' 'csfd-meta/*.zip' \
		'csfd-meta/requirements-dev.txt' 'csfd-meta/pytest.ini' \
		'csfd-meta/Makefile' 'csfd-meta/.claude/*' \
		'csfd-meta/*.iml' '*/__pycache__/*' 'csfd-meta/.pytest_cache/*'

clean:
	rm -f $(NAME)-$(VERSION).zip

# Note: Kodi expects the addon id (metadata.csfd) as the top folder inside
# the zip. If your working dir is named csfd-meta (as in this repo), rename
# it to metadata.csfd before zipping, or adjust the zip rule to stage the
# files under a metadata.csfd/ directory. Verify by opening the built zip.
