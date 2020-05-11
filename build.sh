#!/usr/bin/sh

# Run this file from the directory it's in.
# Creates dcnl.ankiaddon (preventing overwriting).

if [ -e "dcnl.ankiaddon" ]
then
  echo "Please rename or delete dcnl.ankiaddon"
  exit
fi

zip -rj dcnl.ankiaddon dcnl --exclude \*.pyc \*pycache\*
