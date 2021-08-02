#!/bin/bash

# Download the last three months of 1-minute data
# https://www.alphavantage.co/documentation/#intraday-extended

# Example:
#	source ./tickers.conf
#	./download-history-data.sh $SMALL_MID2

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

# Get dates for the most recent three months
today=$( date +'%Y-%m-%d' --date='-1 day' )
last_month=$( date +'%Y-%m' --date='-1 months' )
two_months_ago=$( date +'%Y-%m' --date='-2 months' )

BASE_URL='https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY_EXTENDED&interval=1min&adjusted=false'

# Download the latest three months of 1-minute candle data
# Notes:
# - Candle data is in CSV format: "time,open,high,low,close,volume"
# - Only data up to the previous trading day is available
# - Monthly history data from alphavantage is separated into monthly "slices," however
#    the slices stop and start on today's date. So a slice may be from 04-12-2021 to 04-12-2021
#    instead of on the month boundary. Yes, that is stupid.
# - The data is also from the most recent day to the last day. We use tac to reverse this.
# - We also use 'grep -v' to strip out the headers "time,open,high,low,close,volume"
function download_ticker() {

	ticker=$1

	curl --silent "${BASE_URL}&symbol=${ticker}&slice=year1month3&apikey=${API_KEY}" | grep -v 'time,open' | tac > "monthly-csv/${ticker}-3months-${today}.csv"
	curl --silent "${BASE_URL}&symbol=${ticker}&slice=year1month2&apikey=${API_KEY}" | grep -v 'time,open' | tac >> "monthly-csv/${ticker}-3months-${today}.csv"
	curl --silent "${BASE_URL}&symbol=${ticker}&slice=year1month1&apikey=${API_KEY}" | grep -v 'time,open' | tac >> "monthly-csv/${ticker}-3months-${today}.csv"

}

echo 'Downloading 3-months of 1-minute data for the following tickers:'
echo "$1"
echo

tickers=$( echo -n $tickers | sed 's/,/ /g' )
for t in $tickers; do

	echo "$t"
	download_ticker $t &

	sleep 2

done


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
