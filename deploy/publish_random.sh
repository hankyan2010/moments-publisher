#!/bin/bash
# 随机延迟发布,避免被微信识别为机器人定时操作。
# launchd 在每个时段「窗口起点」触发本脚本,本脚本随机 sleep 0-60 分钟再真正发。
#
# 用法: publish_random.sh <morning|noon|evening>

set -u
SLOT="${1:?需要 slot 参数}"
ROOT="$HOME/moments-publisher"
LOG="$ROOT/logs/publish-random-$SLOT.log"

# 0-3600 秒随机 (0-60 分钟)
SLEEP_SEC=$(python3 -c "import random; print(random.randint(0, 3600))")
SLEEP_MIN=$((SLEEP_SEC / 60))

echo "[$(date '+%F %T')] $SLOT 随机延迟 ${SLEEP_MIN} 分钟 (${SLEEP_SEC}s)" >> "$LOG"
sleep "$SLEEP_SEC"

echo "[$(date '+%F %T')] $SLOT 实际发布开始" >> "$LOG"
cd "$ROOT" && /usr/bin/env python3 src/daily.py publish-slot "$SLOT" >> "$LOG" 2>&1
EC=$?
echo "[$(date '+%F %T')] $SLOT 完成 exit=$EC" >> "$LOG"
exit $EC
