#!/bin/sh
NC='\033[0m'
FAIL='\033[0;31m'
PASS='\033[0;32m'

result=0
for d in resources/language/*/*.po; do
  printf "Checking %-70s" "${d}"
  xgettext "$d" 2>out
  rc=$?
  if [ $rc = 1 ]; then
    echo "[ ${FAIL}FAIL${NC} ]"
    while read -r i; do
      printf "  %s\n" "$i"
    done <out
    result=1
  else
    echo "[ ${PASS} OK ${NC} ]"
  fi
done

rm -f messages.po
rm -f out
exit $result
