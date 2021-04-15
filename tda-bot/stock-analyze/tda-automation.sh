#!/bin/bash

# This script uses generate-csv.pl to process files created by "tda-rsi-gobot.py --analyze"
#  and generate a CSV file with all the relevant data. We can then import this data into
#  Excel and sort to find the best stocks to use for the week.

command=${1-"analyze"}
usd=${2-"1000"}

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
		while
			echo "$i"
			sleep 2 # Avoid throttling
			./tda-gobot-analyze.py  --algo=rsi,stochrsi --stoploss --decr_threshold=1.5 --days=5,10 \
						--rsi_type=ohlc4 --rsi_period=14 --stochrsi_period=128 --rsi_k_period=128 --rsi_d_period=3 --rsi_slow=3 \
						"$i" > "./${logdir}/${i}.log.txt"

			if [ "$?" -ne "0" ]; then
				sleep 5
				continue
			fi

		[[ "$?" -ne "0" ]]
		do true; done

	done
	echo -e "\nDone!"
}


# Generate the CSV files
generate_csv () {

	cd "$logdir"
	echo -n 'Generating stonks-analyze-all.csv ... '
	echo 'Stock,Algorithm,Days,Average Txs,Success Rate,Fail Rate,Average Gain,Average Loss,Avg Gain/Share,Stock Rating' > stonks-analyze-all.csv
	for i in *.log.txt; do
		if [ `grep -c 'no possible trades' $i` -eq 0 -a `grep -c 'Not enough data' $i` -eq 0 ]; then
			cat $i | ./generate-csv.pl >> stonks-analyze-all.csv
		fi
	done
	echo "Done"

	echo -n 'Generating stonks-analyze-topstocks.csv ... '
	echo 'Stock,Algorithm,Days,Average Txs,Success Rate,Fail Rate,Average Gain,Average Loss,Avg Gain/Share,Stock Rating' > stonks-analyze-topstocks.csv
	for i in *.log.txt; do

#		if [ `grep -ci 'very good' $i`  -ge 2 ]; then
#			cat $i | ./generate-csv.pl >> stonks-analyze-topstocks.csv
#			#echo $i | sed 's/\.log\.txt//'
#		fi

		rsi_5_day=$(grep 'rating' $i | head -1)
		stochrsi_5_day=$(grep 'rating' $i | tail -2 | head -1)
		if [ `echo -n "$rsi_5_day" | grep -ci 'very good'` -eq 1 -a `echo -n "$stochrsi_5_day" | grep -ci 'very good'` -eq 1 ]; then
			cat $i | ./generate-csv.pl >> stonks-analyze-topstocks.csv
			#echo $i | sed 's/\.log\.txt//'
		fi
	done
	echo "Done"
}


# Restart all the gobots with the latest/greatest tickers
restart_bots () {


	# Find the top stocks for the last five days
	stonks=""
	for i in ${logdir}/*.log.txt; do
		rsi_5_day=$(grep 'rating' $i | head -1)
		stochrsi_5_day=$(grep 'rating' $i | tail -2 | head -1)
		if [ `echo -n "$rsi_5_day" | grep -ci 'very good'` -eq 1 -a `echo -n "$stochrsi_5_day" | grep -ci 'very good'` -eq 1 ]; then
			ticker=$( echo -n $i | sed 's/\.log\.txt//' )
			stonks="${stonks} $ticker"
		fi
	done

	# Kill all existing bots
	pkill -f tda-rsi-gobot.py

	# Check if we should dump the existing portfolio
	echo "Dump portfolio? (yes/no)"
	read
	input=$(echo -n ${REPLY} | tr '[:upper:]' '[:lower:]')
	if [ "$input" == 'yes' ]; then
		./tda-sell-stock.py --panic --force
	fi

	# Run the bots
	for ticker in $stonks; do
		nohup ./tda-rsi-gobot.py --algo=stochrsi --multiday --short --stoploss --decr_threshold=1.5 \
			--num_purchases=20 --max_failed_txs=10 --max_failed_usd=300 \
			--rsi_high_limit=80 --rsi_low_limit=20 --rsi_period=128 --rsi_k_period=128 --rsi_d_period=3 --rsi_slow=3 \
			$ticker $usd 1>>log.txt 2>&1 &

		disown
		sleep 2
	done

}


# Main
if [ "$command" == 'analyze' ]; then
	analyze
	echo
	generate_csv

elif [ "$command" == 'restart' ]; then
	restart_bots

elif [ "$command" == 'generate-csv' ]; then
	generate_csv

else
	echo "Unknown option: $command"

fi


