#!/bin/bash

## This is a helper script that:
##
## 1 - Iterates through all the AdjClose files in DATA/ and runs them through
##     pfopt-real.py. Output is redirected to OUTPUT/<filename>.out
##
## 2 - Iterates through all the files in OUTPUT/<filename>.out and runs them
##     through pfopt-parse-output.pl to get the top 5 stocks from each sector.
##     The output is redirected to OUTPUT/<filename>-top5.out
##
## 3 - Combines all the OUTPUT/<filename>-top5.out into one big list, and then
##     Runs this through pfopt-real.py again. Output is redirated to
##     OUTPUT/final.out

# Clear the OUTPUT/ directory
rm -f OUTPUT/*

childpids=()
for i in DATA/*AdjClose*.csv; do
	filename=$( echo -n $i | sed 's/\.csv//' )
	filename=$( echo -n $filename | sed 's/DATA\///' )

	echo "Processing" $(echo -n "$i" | sed 's/DATA\///') "=> OUTPUT/${filename}.out"
	./pfopt-real.py "$i" 1> OUTPUT/${filename}.out 2>&1 &
	childpids+=("$!")
done

## Wait for all child processes to finish
let wait=1
while [ $wait -eq 1 ]; do
	let wait=0
	for i in ${childpids[@]}; do
		if `ps --pid $i 1>/dev/null 2>&1` ; then
			let wait=1
			break
		fi
	done

	if [ $wait -eq 1 ]; then
		echo "PID $i exists, sleeping..."
		sleep 60
	fi
done
echo

# Process the output of pfopt-real.py to collect top 5 tickers from each sector.
for i in OUTPUT/*.out; do
	filename=$( echo -n $i | sed 's/\.out//' )
	filename=$( echo -n $filename | sed 's/OUTPUT\///' )
	echo "Parsing" $(echo -n "$i" | sed 's/OUTPUT\///') "=> OUTPUT/${filename}-top5.out"

	./pfopt-parse-output.pl "$i" > OUTPUT/${filename}-top5.out
done

# Finally, collect the top 5 tickers and run them through pfopt-real.py
rm -f OUTPUT/FINAL-top5.out
cat OUTPUT/*-top5.out >> OUTPUT/FINAL-top5.out
#top5=$(cat OUTPUT/*-top5.out)

#TODO
# Need to modify pfopt-real.py to accept just a list of tickers instead of full csv files with adjclose pricing
# Need to make sure to pass tickers in a way acceptable by pfopt-real.py

# TODO
#  Afterward, we are left with just a list of stock tickers. We need to modify
#  pfopt-real (or copy it as another script) to download all the history data again :(

