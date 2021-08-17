#!/bin/bash

start_date=${1-''}

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
end_date=$( ls monthly-csv/${end_date}-3months-*.pickle | sed "s/monthly\-csv\/$end_date\-3months\-//" | sed 's/\.pickle//' )

rm -f ./results/*
cd ../
for t in $tickers; do

	echo $t;
	./gobot-test.py --all --ifile stock-analyze/monthly-csv/${t}-3months-${end_date}.pickle --ofile stock-analyze/results/${t} \
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

list=""
for i in $( echo -e "$algo1\n$algo2" ) ; do
	if `echo -n $i | grep -q 'stochrsi'` ; then
		continue
	fi

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

