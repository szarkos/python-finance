#!/bin/bash

# Download the last three months of 1-minute data
# https://www.alphavantage.co/documentation/#intraday-extended

# Example:
#	source ./tickers.conf
#	./download-history-1min.sh $SMALL_MID2

tickers=${1-''}
interval=${2-'1min'} # 1min, 5min, 15min, 30min, 60min
months=${3-'3'}

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

BASE_URL='https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY_EXTENDED&adjusted=false'
BASE_URL="${BASE_URL}&interval=${interval}"

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

	let i=$months
	if [ "$i" -eq 1 ]; then
		curl --silent "${BASE_URL}&symbol=${ticker}&slice=year1month1&apikey=${API_KEY}" | grep -v 'time,open' | tac > "monthly-${interval}-csv/${ticker}-1months-${today}.csv"

	else

		echo -n "" > "monthly-${interval}-csv/${ticker}-${months}months-${today}.csv"
		while [ "$i" -gt 0 ]; do
			curl --silent "${BASE_URL}&symbol=${ticker}&slice=year1month${i}&apikey=${API_KEY}" | grep -v 'time,open' | tac >> "monthly-${interval}-csv/${ticker}-${months}months-${today}.csv"
			let i=$i-1
		done

	fi
}

if [ "$tickers" == 'CHECK_TICKERS' ]; then

	echo "Checking CSV files for errors..."

	for i in monthly-${interval}-csv/*.csv; do
		errors=$( egrep --ignore-case --count '(thank|error)' $i )
		if [ "$errors" != "0" ]; then

			ticker=$( echo -n $i | sed 's/monthly-[0-9]*min-csv\///' | sed 's/-.*//' | tr '\n' '' )

			echo "$ticker"
			download_ticker "$ticker"
		fi
	done

	exit
fi


echo "Downloading ${months}-months of 1-minute data for the following tickers:"
echo "$1"
echo

# Avoid throttling
slp=2
if [ "$(echo "$months > 5" | bc)" == 1 ]; then
	slp=5
fi

tickers=$( echo -n $tickers | sed 's/,/ /g' )
for t in $tickers; do

	echo "$t"
	download_ticker $t &

	sleep $slp

done

# Check downloaded .csv files for errors
sleep 20
./download-history-1min.sh CHECK_TICKERS $interval $months

