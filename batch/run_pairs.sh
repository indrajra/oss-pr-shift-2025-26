#!/bin/zsh
# For each repo in a list, run the 2023-24 window and then the 2025-26 window before moving on,
# so every finished repo has both windows. Rerunnable: finished runs are skipped and fetches resume.
#
#   batch/run_pairs.sh batch/repos_sample.txt
#   touch batch/STOP          # stop cleanly after the run in progress; delete the file to allow a restart
cd "${0:A:h}/.." || exit 1
export GH_TOKEN=$(gh auth token)
repos=${1:-batch/repos_sample.txt}
windows=(
  "results_2023 cache_2023 2023-01-09 2024-08-19"
  "results cache 2025-01-06 2026-08-17"
)

while read -r repo; do
  [[ -z $repo ]] && continue
  slug=${repo/\//__}
  for w in $windows; do
    if [[ -f batch/STOP ]]; then
      echo "$(date '+%F %T') stopped (batch/STOP exists)"
      exit 0
    fi
    read -r out cache start end <<< $w
    mkdir -p $out/_batch
    if [[ -f $out/_batch/$slug.done ]]; then
      echo "$(date '+%F %T') skip $repo $start (done)"
      continue
    fi
    echo "$(date '+%F %T') start $repo $start"
    if .venv/bin/python -m prwords $repo --out $out --cache $cache --start $start --end $end \
        > $out/_batch/$slug.log 2>&1; then
      touch $out/_batch/$slug.done
      echo "$(date '+%F %T') done $repo $start"
    else
      echo "$(date '+%F %T') FAILED $repo $start (see $out/_batch/$slug.log)"
    fi
  done
done < $repos
echo "$(date '+%F %T') batch finished"
