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


# Run a new backtest and email the results
cd ~/python-finance/tda-bot/stock-analyze/
source tickers.conf
tickers="$HIGH_NATR"
tickers=$( echo -n $tickers | sed 's/,/ /g' )

rm -f results/*
monthly_data=$( ls monthly-1min-csv/*.pickle | tail -1 | sed 's/monthly-1min-csv\///' | sed 's/[A-Z]*\-//' )
for t in $tickers; do
	./gobot-test.py --ifile=monthly-1min-csv/${t}-${monthly_data} \
			--ofile=results/${t} \
			--opts=" --weekly_ifile=weekly-csv/${t}-weekly-2019-2021.pickle --daily_ifile=./daily-csv/${t}-daily-2019-2021.pickle "
done

cur_time=$(TZ="America/Los_Angeles" date)
test_data=$(./summarize-results.sh results)
echo "${test_data}" | mail -s "Gobot Backtest (${cur_time})" stonks@sentry.net


