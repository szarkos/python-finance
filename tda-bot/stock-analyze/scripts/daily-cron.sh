#!/bin/bash

cd ~/python-finance/tda-bot

# Check email for TDA alerts and update tickers.conf
~/python-finance/tda-bot/stock-analyze/scripts/monitor-alerts-imap.py --tda_alert_name='Gobot Stock Scanner - NATR' --ticker_group=HIGH_NATR
~/python-finance/tda-bot/stock-analyze/tickers.conf /stonks/tickers.conf

git add ~/python-finance/tda-bot/stock-analyze/tickers.conf
git commit -m 'Update tickers.conf'
git push

# Refresh all the monthly/daily/weekly backtest data every day except on Sunday
day="$(date +'%w')"
if [ "$day" != 0 ]; then
	~/python-finance/tda-bot/stock-analyze/scripts/refresh-data.sh
fi

