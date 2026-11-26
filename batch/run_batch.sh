#!/bin/zsh
# Run prwords on every repo in a list, one at a time.
# Rerunnable: finished repos are skipped, and an interrupted fetch resumes from the cache.
#
#   batch/run_batch.sh                                    # batch/repos.txt, default window, results/ and cache/
#   REPOS=batch/repos_2023.txt OUT=results_2023 CACHE=cache_2023 \
#     START=2023-01-09 END=2024-08-19 batch/run_batch.sh  # an earlier comparison window
cd "${0:A:h}/.." || exit 1
export GH_TOKEN=$(gh auth token)
repos=${REPOS:-batch/repos.txt}
out=${OUT:-results}
cache=${CACHE:-cache}
window=()
[[ -n $START ]] && window+=(--start $START)
[[ -n $END ]] && window+=(--end $END)
logs=$out/_batch
mkdir -p $logs

while read -r repo; do
  [[ -z $repo ]] && continue
  slug=${repo/\//__}
  if [[ -f $logs/$slug.done ]]; then
    echo "$(date '+%F %T') skip $repo (done)"
    continue
  fi
  echo "$(date '+%F %T') start $repo"
  if .venv/bin/python -m prwords $repo --out $out --cache $cache $window > $logs/$slug.log 2>&1; then
    touch $logs/$slug.done
    echo "$(date '+%F %T') done $repo"
  else
    echo "$(date '+%F %T') FAILED $repo (see $logs/$slug.log)"
  fi
done < $repos
echo "$(date '+%F %T') batch finished"
