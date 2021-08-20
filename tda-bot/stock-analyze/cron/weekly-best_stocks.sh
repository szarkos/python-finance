#!/bin/bash

# By default, $start_date is two weeks ago from today
start_date=${1-$(date +'%Y-%m-%d' --date='-2 weeks')}

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/.."

# Gain threshold - net gain (per share) required to add stock to the final list
gain_threshold="0.07"

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
	start="--start_date=${start_date}"
fi

end_date=$( echo -n "$tickers" | awk '{print $1}' )
end_date=$( ls monthly-1min-csv/${end_date}-3months-*.pickle | sed "s/monthly\-csv\/$end_date\-3months\-//" | sed 's/\.pickle//' )

rm -f ./results/*
cd ../
for t in $tickers; do

	echo $t;
	./gobot-test.py --all --ifile stock-analyze/monthly-1min-csv/${t}-3months-${end_date}.pickle --ofile stock-analyze/results/${t} \
		--opts=" --weekly_ifile stock-analyze/weekly-csv/${t}-weekly-2019-2021.pickle --exit_percent=1 ${start} "

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


list=""
for i in $( echo -e "${algo1}\n${algo2}" ) ; do
	if `echo -n $i | grep --silent 'stochrsi'` ; then
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

	# Check if ticker is currently blacklisted
	blacklist=$( ${parent_path}/../../tda-quote-stock.py --check_blacklist $ticker )
	if [ "$blacklist" == "True" ]; then
		i=""
	fi

	if [ "$i" == "" ]; then
		continue
	fi

	# Finally, add stock to list if it's net gain is above the $gain_threshold
	gain=$(echo -n $i | awk -F, '{print $2}' )
	if (( $( echo "$gain" ' >= ' "$gain_threshold" | bc -l ) )); then
		list="$list "$(echo $i | awk -F, '{print $1}')
	fi
done

list=$( echo "$list" | sed 's/^\s//' | sed 's/ /\n/g' | sort | uniq )


# Write CUR_SET to tickers.conf
echo -e "\n# "$(date +%Y-%m-%d) >> tickers.conf
echo -en "CUR_SET='" >> tickers.conf
echo -n "$list" | tr '\n' ',' | sed 's/^,//' | sed 's/,$//' >> tickers.conf
echo -e "'\n" >> tickers.conf

