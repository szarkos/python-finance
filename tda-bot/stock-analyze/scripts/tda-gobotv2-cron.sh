#!/bin/bash

cd ~/python-finance/tda-bot
mkdir ./logs 2>/dev/null

# Check for updates
git pull

# Run tda-gobotV2 every day except on Saturday and Sunday
# Gobot will check to see if it's a weekday market holiday
day="$(date +'%w')"
if [ "$day" != "0" -a "$day" != "6" ]; then
	nohup ~/python-finance/tda-bot/stock-analyze/scripts/tda-gobotv2-automation.sh 1>logs/nohup.log 2>&1 &
	disown
fi
