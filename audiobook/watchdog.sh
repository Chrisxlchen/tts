#!/bin/zsh
# Pauses the audiobook build while the Mac runs short of memory or disk, and resumes it once there is room again.
#   nohup ./watchdog.sh > /dev/null 2>&1 < /dev/null & disown       log: work/watchdog.log
# Pausing is SIGSTOP/SIGCONT on the build, acting and IndexTTS-2 processes: nothing is lost, macOS can page
# their memory out for the user's own apps, and run.sh just waits.
cd "${0:A:h}"
LOG=work/watchdog.log
MIN_FREE_PCT=5      # memory_pressure's "free percentage" below this, or the kernel at critical, pauses
RESUME_FREE_PCT=20  # and it has to be back above this for RESUME_CHECKS checks in a row to resume
MIN_DISK_GB=8
RESUME_DISK_GB=12
RESUME_CHECKS=4
EVERY_S=30

pids() { pgrep -f "audiobook.py (act|build) |act_index.py " }
say() { echo "$(date '+%F %T') $1" >> $LOG; osascript -e "display notification \"$1\" with title \"有声书\"" 2>/dev/null }

paused=0 calm=0
while true; do
  free=$(memory_pressure | awk '/free percentage/ {gsub("%", "", $NF); print $NF}')
  level=$(sysctl -n kern.memorystatus_vm_pressure_level)  # 1 normal, 2 warning, 4 critical
  disk=$(df -g /System/Volumes/Data | awk 'NR==2 {print $4}')
  if (( free < MIN_FREE_PCT || level >= 4 || disk < MIN_DISK_GB )); then
    calm=0
    if (( ! paused )) && [[ -n "$(pids)" ]]; then
      kill -STOP $(pids) 2>/dev/null
      paused=1
      say "暂停生成：内存剩 ${free}%（压力 ${level}），磁盘剩 ${disk} GB"
    fi
  elif (( paused )); then
    kill -STOP $(pids) 2>/dev/null  # anything started meanwhile waits too
    if (( free > RESUME_FREE_PCT && level < 4 && disk >= RESUME_DISK_GB )); then calm=$((calm + 1)); else calm=0; fi
    if (( calm >= RESUME_CHECKS )); then
      kill -CONT $(pids) 2>/dev/null
      paused=0 calm=0
      say "继续生成：内存剩 ${free}%，磁盘剩 ${disk} GB"
    fi
  fi
  sleep $EVERY_S
done
