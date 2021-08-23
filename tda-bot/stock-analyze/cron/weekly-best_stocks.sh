#!/bin/bash

# By default, $start_date is two weeks ago from today
start_date=${1-$(date +'%Y-%m-%d' --date='-2 weeks')}

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/.."

# Gain threshold - net gain (per share) required to add stock to the final list
# Typically algo1 is less restrictive and more risky, so only include tickers
#  that have a higher gain threshold.
algo1_gain_threshold="0.2"
algo2_gain_threshold="0.08"

# First, refresh all the 3-month data
./cron/refresh-data.sh


# Run the test script for each ticker
source ./tickers.conf
tickers=$BIGLIST
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

rm -f ./results/*
cd ../
for t in $tickers; do

	echo $t;
	./gobot-test.py --all --ifile=stock-analyze/monthly-1min-csv/${t}-3months-${end_date}.pickle --ofile=stock-analyze/results/${t} \
		--opts=" --weekly_ifile=stock-analyze/weekly-csv/${t}-weekly-2019-2021.pickle --exit_percent=1 $startdate "

done
cd "${parent_path}/.."


# Generate results summary
data=$( ./summarize-results.sh ticker-net-gain )


# Parse and sort results
# This part is very dependent on the notion that we are only testing for two good
#  indicator groups (i.e. stochrsi_dmi_simple and stochrsi_aroonosc_dmi_simple)
algo1=$( for i in "$data"; do echo "$i" | awk -F ',' '{print $1","$4}'; done )
algo2=$( for i in "$data"; do echo "$i" | awk -F ',' '{print $1","$7}'; done )

algo1=$( echo "$algo1" | sort -bt ',' -k1,2 )
algo2=$( echo "$algo2" | sort -bt ',' -k1,2 )


# Create list of tickers that lost money
loss_list=""
algo1_loss=$( for i in "$data"; do echo "$i" | awk -F ',' '{print $1","$3}'; done )
algo2_loss=$( for i in "$data"; do echo "$i" | awk -F ',' '{print $1","$6}'; done )
for i in $( echo -e "${algo1_loss}\n${algo2_loss}" ) ; do
	net_loss=$(echo -n $i | awk -F, '{print $2}' )

	if `echo -n $net_loss | grep --silent 'stochrsi'` ; then
		continue
	fi

	if (( $( echo "$net_loss" ' > 0' | bc -l ) )); then
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

	# Check if ticker is currently blacklisted
	cd ${parent_path}/../../
	blacklist=$( ./tda-quote-stock.py --check_blacklist $ticker )
	cd "${parent_path}/.."
	if [ "$blacklist" == "True" ]; then
		continue
	fi

	# Finally, add stock to the list if it has made it this far
	list="$list "$(echo $i | awk -F, '{print $1}')

done

## ALGO2
for i in $( echo -e "${algo2}" ) ; do
	if `echo -n $i | grep --silent 'stochrsi'` ; then
		continue
	fi

	# Check if it's net gain is below the $gain_threshold
	gain=$(echo -n $i | awk -F, '{print $2}' )
	if (( $( echo "$gain" ' < ' "$algo2_gain_threshold" | bc -l ) )); then
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

	# Check if ticker is currently blacklisted
	cd ${parent_path}/../../
	blacklist=$( ./tda-quote-stock.py --check_blacklist $ticker )
	cd "${parent_path}/.."
	if [ "$blacklist" == "True" ]; then
		continue
	fi

	# Finally, add stock to the list if it has made it this far
	list="$list "$(echo $i | awk -F, '{print $1}')

done

list=$( echo "$list" | sed 's/^\s//' | sort | uniq )


# Write CUR_SET to tickers.conf
echo -e "\n# "$(date +%Y-%m-%d) >> tickers.conf
echo -en "CUR_SET='" >> tickers.conf
echo -n "$list" | tr '\n' ',' | sed 's/^,//' | sed 's/,$//' >> tickers.conf
echo -e "'\n" >> tickers.conf
