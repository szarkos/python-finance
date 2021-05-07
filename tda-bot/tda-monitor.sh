#!/bin/bash

# Usage:
#  ./tda-automation.sh <monitor]> <TX-LOG-DIR>

command=${1-"monitor"}
command=${2-"TX_LOGS"}

############################################################################################
# Monitor the logs
while [ 1 ]; do

	printf "\033c"
	echo -e "Stock\t% Change\tLast Price\tNet Change\tBase Price\tOriginal Base Price\tQuantity\tShort\tSold"

	for i in ${2}/*; do
		line=$( cat "$i" | awk -F : '{print $1"\t"$2"%\t\t"$3"\t\t"$4"\t\t"$5"\t\t"$6"\t\t\t"$7"\t\t"$9"\t"$8}' )
		echo -e "$line"
	done

	echo

	let net_change=0
	for i in ${2}/*; do
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

