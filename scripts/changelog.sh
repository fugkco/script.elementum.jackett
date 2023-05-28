#!/bin/bash

set -eu

cat="$(command -v cat)"
export GIT_PAGER="$cat"

echo "Changelog"
echo "==============="

previous_tag=0
while read -r current_tag; do
  if [[ "$previous_tag" != 0 ]]; then
    tag_date=$(git log -1 --pretty=format:'%ad' --date=short ${previous_tag})
    printf "[B]%s[/B] (%s)\n" "${previous_tag}" "${tag_date}"
    cmp="${current_tag}...${previous_tag}"
    [[ $current_tag == "LAST" ]] && cmp="${previous_tag}"
    git log "$cmp" --no-merges --pretty=format:' - %s' --reverse
    printf "\n\n"
  fi
  previous_tag="${current_tag}"
done < <(git tag -l | sort -u -r -V; echo LAST)
