#!/bin/bash

# Trap errors
trap 'exit $?' ERR

VERSION="$(python2 -c 'from mcomix.constants import VERSION; print VERSION')"
MAINTAINER="https://sourceforge.net/projects/mcomix/"

xgettext --language=Python -omcomix.pot --output-dir=mcomix/messages/ --add-comments=TRANSLATORS \
    --from-code=utf-8 --package-name=MComix --package-version="$VERSION" \
    --msgid-bugs-address="$MAINTAINER" \
    $(git ls-files '*.py')

for pofile in mcomix/messages/*/LC_MESSAGES/*.po
do
    # Merge message files with master template.
    msgmerge --update --backup=none "$pofile" mcomix/messages/mcomix.pot
    # Compile translation.
    msgfmt "$pofile" -o "${pofile%.po}.mo"
done
