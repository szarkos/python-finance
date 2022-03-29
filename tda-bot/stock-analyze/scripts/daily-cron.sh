#!/bin/bash

cd ~/python-finance/tda-bot

# Backup log file
cp ./logs/gobot-v2.log logs/gobot-v2-$(date +'%Y%m%d').log
xz -9 ./logs/gobot-v2-$(date +'%Y%m%d').log

# Check email for TDA alerts and update tickers.conf
~/python-finance/tda-bot/stock-analyze/scripts/monitor-alerts-imap.py --tda_alert_name='Gobot Stock Scanner - NATR' --ticker_group=HIGH_NATR

## Update full ticker list ##
# Cleanup first
mkdir ~/python-finance/tda-bot/stock-analyze/scripts/tickers-history 2>/dev/null
rm -f ~/python-finance/tda-bot/stock-analyze/scripts/tickers-history/*.conf 2>/dev/null

# Pull all the versions of tickers.conf from the last few months
cd ~/python-finance/tda-bot/stock-analyze
hist=$( git log --since=2021-11-01 | grep commit | awk '{print $2}' | tr '\n' ' ' )
for i in $hist; do
	git show ${i}:./tickers.conf | tr '\r' '\n' > ./scripts/tickers-history/tickers-commit${i}.conf
done

# Parse the HIGH_NATR variable from each tickers.conf version and output to a single file
cd ~/python-finance/tda-bot/stock-analyze/scripts/tickers-history
for i in tickers-commit* ; do
	hn=$( egrep '^HIGH_NATR=' $i | grep -v 'CUR_SET' )
	echo -e "$hn\n" >> ./tickers-all.conf

	hn=$( egrep '^HIGH_NATR=' $i | grep -v 'CUR_SET' | sed 's/HIGH_NATR=//g' | sed 's/"//g' | sed "s/'//g" | tr '\n' ',' | sed 's/\s//g' )
	echo -e "$hn\n" >> ./tickers-final.conf

done

# Finally sort of uniqify all the tickers, and output result
final=$( cat tickers-final.conf )
final=$( echo -n "$final" | tr ',' '\n' | sort | uniq | tr '\n' ',' | sed 's/^,//' | sed 's/,$//' )
final=$( echo -n "$final" | sed 's/,[A-Z]*\/[A-Z]*,/,/g' ) # Tickers like OXY/WS slipped in at some point
final="'"${final}"'"
#echo "$final"
sed -i "s/BACKTEST_NATR=.*/BACKTEST_NATR=${final}/" ~/python-finance/tda-bot/stock-analyze/tickers.conf

cp ~/python-finance/tda-bot/stock-analyze/tickers.conf /stonks/tickers.conf
git add ~/python-finance/tda-bot/stock-analyze/tickers.conf
git commit -m 'Update tickers.conf'
git push
## End update full ticker list ##


# Refresh all the monthly/daily/weekly backtest data every day except on Sunday
day=$( date +'%w' )
if [ "$day" != "0" ]; then
	~/python-finance/tda-bot/stock-analyze/scripts/refresh-data.sh
fi


# Run a new backtest and email the results
cd ~/python-finance/tda-bot/stock-analyze/
source tickers.conf
tickers="$BACKTEST_NATR"
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


# Inform on which tickers are not functioning properly with each algo
scenarios=$(./gobot-test.py --print_scenarios)
bad_tickers=''
for i in $scenarios; do
	bad=$( egrep '(Success|Total)' results/*-${i} | grep 31m | sed 's/results\///' | sed 's/\-.*//' | sort | uniq | tr '\n' ',' | sed 's/,$//' )
	bad_tickers="${bad_tickers}\n${i}\n${bad}\n"
done

# Email the data
echo -e "${bad_tickers}\n\n\n${test_data}" | mail -s "Gobot Backtest (${cur_time})" stonks@sentry.net

