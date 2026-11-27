#!/bin/zsh
# Run at login (see the LaunchAgent below): restarts the watchdog and, if a job is queued in work/current_job.sh,
# that job, unless either is already running. Finished chapters are never redone, so a resumed job carries on.
#   ~/Library/LaunchAgents/com.xlchen.audiobook.resume.plist runs this with RunAtLoad.
cd "${0:A:h}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
pgrep -f "/bin/zsh ./watchdog.sh" > /dev/null || nohup ./watchdog.sh > /dev/null 2>&1 < /dev/null &
if [[ -x work/current_job.sh ]] && ! pgrep -f "audiobook.py (act|build) " > /dev/null; then
  echo "$(date '+%F %T') resuming $(readlink work/current_job.sh)" >> work/watchdog.log
  nohup ./work/current_job.sh > /dev/null 2>&1 < /dev/null &
fi
