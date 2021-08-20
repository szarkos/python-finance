#!/bin/bash

# Download the last three months of 1-minute data
# https://www.alphavantage.co/documentation/#intraday-extended

# Example:
#	source ./tickers.conf
#	./download-history-weekly.sh $SMALL_MID2

tickers=${1-''}

if [ "$tickers" == '' ]; then
	echo "Please provide a list of tickers (comma separated)"
	exit
fi

API_KEY=''
source ./.env	# Put API_KEY here
if [ "$API_KEY" == "" ]; then
	echo "I need an API key, exiting"
	exit
fi


# WEEKLY CHARTS
cur_year=$( date +'%Y' )
prev_year1=$( date +'%Y' --date='-1 year' )
prev_year2=$( date +'%Y' --date='-2 year' )
function download_weekly() {
	ticker=$1

	curl --silent "https://www.alphavantage.co/query?function=TIME_SERIES_WEEKLY&symbol=${ticker}&datatype=csv&apikey=${API_KEY}" | \
			grep -v timestamp,open | tac | \
			egrep "(^${prev_year2}\-|^${prev_year1}\-|^${cur_year}\-)" > "weekly-csv/${ticker}-weekly-${prev_year2}-${cur_year}.csv"

}

echo 'Downloading weekly data for the following tickers:'
echo "$1"
echo

tickers=$( echo -n $tickers | sed 's/,/ /g' )
for t in $tickers; do

	echo "$t"
	download_weekly $t &

	sleep 2

done
