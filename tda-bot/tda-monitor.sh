#!/bin/bash

# Usage:
#  ./tda-automation.sh <TX-LOG-DIR>
log_dir=${1-"TX_LOGS_v2"}

############################################################################################
# Monitor the logs
while [ 1 ]; do

	printf "\033c"
	echo -e "Stock\t\t% Change\tLast Price\tNet Change\tBase Price\tOriginal Base Price\tQuantity\tShort\tSold\tEntry\t\t\tExit"

	for i in $(ls -t ${log_dir}/*.txt); do
		short=$( cat "$i" | awk -F : '{print $9}' )
		entry_price=$( cat "$i" | awk -F : '{print $10}' )
		exit_price=$( cat "$i" | awk -F : '{print $11}' )
		if [ "$entry_price" == "" ]; then
			entry_price='0000-00-00 00:00'
		fi
		if [ "$exit_price" == "" ]; then
			exit_price='0000-00-00 00:00'
		fi

		if [ "$short" == True ]; then
			line=$( cat "$i" | awk -F : '{print $1"*\t"$2"%\t\t"$3"\t\t"$4"\t\t"$5"\t\t"$6"\t\t\t"$7"\t\t"$9"\t"$8}' )
		else
			line=$( cat "$i" | awk -F : '{print $1"\t"$2"%\t\t"$3"\t\t"$4"\t\t"$5"\t\t"$6"\t\t\t"$7"\t\t"$9"\t"$8}' )
		fi
		echo -e "${line}\t${entry_price}\t${exit_price}"
	done

	echo

	let net_change=0
	for i in $(ls -t ${log_dir}/*.txt); do
		short=$( cat "$i" | awk -F : '{print $9}' )
		change=$( cat "$i" | awk -F : '{print $4}' | sed -r 's/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g' ) # Net Change
		regexp='^-?[0-9]*([.][0-9]*)?$'
		if ! [[ $change =~ $regexp ]] ; then
			# $change is not a number, corrupted log? Skip it anyway...
			echo "Err: $change is not a number?"
			continue
		fi

		if [ "$short" == "False" ]; then
			net_change=$( echo "$net_change + $change" | bc )
		else
			net_change=$( echo "$net_change - $change" | bc )
		fi
	done

	echo -e "\nTotal Net Change: ${net_change}\n"
	sleep 10

done

