#!/bin/bash

# This script uses generate-csv.pl to process files created by "tda-rsi-gobot.py --analyze"
#  and generate a CSV file with all the relevant data. We can then import this data into
#  Excel and sort to find the best stocks to use for the week.

command=${1-"all"}
stocks_file='./stock-analyze/all-stocks.txt'
logdir=$( dirname "$stocks_file" )

# Use tda-rsi-gobot.py to generate analysis for each stock
analyze () {

	if [ ! -r "$stocks_file" ]; then
		echo "Unable to read ${stocks_file}, exiting."
		exit
	fi

	stocks=()
	while IFS= read -r line; do
		line=$( echo -n "$line" | sed 's/#.*//' | sed 's/\s*\t*//g' )
		if [ ! "$line" == "" ]; then
			stocks+=("$line")
		fi
	done < "$stocks_file"

	echo "Processing ${#stocks[@]} stocks from `basename ${stocks_file}`. This may take a while ..."
	for i in ${stocks[@]}; do
		echo "$i"
		./tda-rsi-gobot.py --analyze "$i" > "./${logdir}/${i}.log.txt"
		sleep 1 # Avoid throttling
	done
	echo -e "\nDone!"
}


# Generate the CSV files
generate_csv () {

	cd "$logdir"
	echo 'Generating stonks-analyze-all.csv ...'
	echo 'Stock,Wins,Losses,Average Txs,Success Rate,Fail Rate,Average Gain,Average Loss,Avg Gain/Share,Stock Rating' > stonks-analyze-all.csv
	for i in *.log.txt; do
		if [ `grep -c 'no possible trades' $i` -eq 0 -a `grep -c 'Not enough data' $i` -eq 0 ]; then
			cat $i | ./generate-csv.pl >> stonks-analyze-all.csv
		fi
	done
	echo "Done"

	echo 'Generating stonks-analyze-topstocks.csv ...'
	echo 'Stock,Wins,Losses,Average Txs,Success Rate,Fail Rate,Average Gain,Average Loss,Avg Gain/Share,Stock Rating' > stonks-analyze-topstocks.csv
	for i in *.log.txt; do
		if [ `grep -ci 'very good' $i`  -eq 2 ]; then
			cat $i | ./generate-csv.pl >> stonks-analyze-topstocks.csv
			#echo $i | sed 's/\.log\.txt//'
		fi
	done
	echo "Done"
}


# Main
if [ "$command" == 'all' ]; then
	analyze
	echo
	generate_csv
elif [ "$command" == 'generate-csv' ]; then
	generate_csv
else
	echo "Unknown option: $command"
fi
