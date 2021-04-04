#!/bin/bash

# Usage:
#  ./tda-automation.sh <all[|monitor]> <stock-file> <amount to invest>
# Default:
#  ./tda-automation.sh all ./stocks.txt 1000

command=${1-"all"}
stonks_file=${2-"./stocks.txt"}
stonk_usd=${3-"1000"}

if [ ! -r "$stonks_file" ]; then
	echo "Error: file $stonks_file does not exist or is not readable."
	exit
fi

regexp='^[0-9]+$'
if ! [[ $stonk_usd =~ $regexp ]] ; then
	echo "Error: argument $stock_usd is not a number."
	exit
fi

stonks=$( cat "$stonks_file" )
gobot_bin="./tda-gobot.py"


############################################################################################
# Run the tda-gobot script
if [ ! "$command" == "monitor" ]; then
	for i in $stonks; do
		echo "Running: ./${gobot_bin} $i $stonk_usd"
		nohup ./${gobot_bin} "$i" "$stonk_usd" 1>>log.txt 2>&1 &
		disown

		sleep 1
	done

	sleep 5
fi

############################################################################################
# Monitor the logs
while [ 1 ]; do

	printf "\033c"
	echo -e "Stock\t% Change\tLast Price\tNet Change\tBase Price\tOriginal Base Price\tQuantity\tSold"

	for i in LOGS/*; do
		line=$( cat "$i" | awk -F : '{print $1"\t"$2"%\t\t"$3"\t\t"$4"\t\t"$5"\t\t"$6"\t\t\t"$7"\t\t"$8}' )
		echo -e "$line"
	done

	echo

	let net_change=0
	for i in LOGS/*; do
		change=$( cat "$i" | awk -F : '{print $4}' | sed -r 's/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g' ) # Net Change
		regexp='^-?[0-9]*([.][0-9]*)?$'
		if ! [[ $change =~ $regexp ]] ; then
			# $change is not a number, corrupted log? Skip it anyway...
			#echo "Err: $change is not a number?"
			continue
		fi

		net_change=$( echo "$net_change + $change" | bc )
	done

	echo -e "\nTotal Net Change: ${net_change}\n"
	sleep 10

done

