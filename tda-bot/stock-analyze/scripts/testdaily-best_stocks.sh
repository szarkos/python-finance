#!/bin/bash

# Test scenario to use (must also be listed in gobot-test.py)
test_scenario='stochrsi_standard_daily_test'

# By default, $start_date is three weeks ago from today
start_date=${1-$(date +'%Y-%m-%d' --date='-3 weeks')}

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/.."

# Gain threshold - net gain (per share) required to add stock to the final list
algo1_gain_threshold="0.2"

# First, refresh all the 3-month data
#./scripts/refresh-data.sh

# Run the test script for each ticker
source ./tickers.conf
tickers=$( ./filter-stocks.py --blacklist --stocks=$BIGLIST | tr '\n' ' ' | sed 's/\s//g' )
tickers=$( echo -n $tickers | sed 's/,/ /g' )

if [ "$tickers" == "" ]; then
	echo "Error: ticker list is empty"
	exit
fi

start=""
if [ "$start_date" != "" ]; then
	startdate="--start_date=${start_date}"
fi

end_date=$( echo -n "$tickers" | awk '{print $1}' )
end_date=$( ls monthly-1min-csv/${end_date}-3months-*.pickle | sed "s/monthly\-1min\-csv\/$end_date\-3months\-//" | sed 's/\.pickle//' )

#rm -f ./results/*
#for t in $tickers; do
#
#	echo $t;
#	./gobot-test.py --ifile=./monthly-1min-csv/${t}-3months-${end_date}.pickle --ofile=./results/${t} \
#		--opts=" --weekly_ifile=./weekly-csv/${t}-weekly-2019-2021.pickle --daily_ifile=./daily-csv/${t}-daily-2019-2021.pickle \
#		--skip_blacklist $startdate " --scenarios=${test_scenario}
#
#done

# Generate results summary
data=$( ./summarize-results.sh results ticker-net-gain $test_scenario )

# Parse and sort results
algo1=$( for i in "$data"; do echo "$i" | awk -F ',' '{print $1","$4}'; done )
algo1=$( echo "$algo1" | sort -bt ',' -k1,2 )

# Create list of tickers that lost money
loss_list=""
algo1_loss=$( for i in "$data"; do echo "$i" | awk -F ',' '{print $1","$3}'; done )
for i in $algo1_loss ; do
	net_loss=$(echo -n $i | awk -F, '{print $2}' )

	if `echo -n $net_loss | grep --silent 'stochrsi'` ; then
		continue
	fi

	if (( $( echo "$net_loss" ' < 0' | bc -l ) )); then  # NET_LOSS is a negative number
		loss_list="$loss_list "$(echo $i | awk -F, '{print $1}')
	fi
done

# Initialize final list of stock tickers
list=""

## ALGO1
for i in $( echo -e "${algo1}" ) ; do
	if `echo -n $i | grep --silent 'stochrsi'` ; then
		continue
	fi

	# Check if it's net gain is below the $gain_threshold
	gain=$(echo -n $i | awk -F, '{print $2}' )
	if (( $( echo "$gain" ' < ' "$algo1_gain_threshold" | bc -l ) )); then
		continue
	fi

	# Check if ticker has been listed in $loss_list
	ticker=$(echo -n $i | awk -F, '{print $1}' )
	for t in "$loss_list"; do
		if [ "$ticker" == "$t" ]; then
			i=""
			break
		fi
	done
	if [ "$i" == "" ]; then
		continue
	fi

	# Finally, add stock to the list if it has made it this far
	list="$list "$(echo $i | awk -F, '{print $1}')

done

list=$( echo "$list" | sed 's/^\s//' | sed 's/ /\n/g' | sort | uniq )

# Write CUR_SET to tickers.conf
echo -e "\n# "$(date +%Y-%m-%d) >> tickers.conf
echo -en "CUR_SET='" >> tickers.conf
echo -n "$list" | tr '\n' ',' | sed 's/^,//' | sed 's/,$//' >> tickers.conf
echo -e "'\n" >> tickers.conf

