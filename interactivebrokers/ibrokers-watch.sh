#!/bin/bash

red='\033[0;31m'
green='\033[0;32m'
reset_color='\033[0m'

old_out=$( curl --silent -u shortstock: ftp://ftp3.interactivebrokers.com/usa.txt )
sleep 5

while [ 1 ]; do

	printf "\033c"
	echo -e "Stock\tShorts Available\tPrev Shorts Available"

	watch=$( cat ./watchlist.txt )
	out=$( curl --silent -u shortstock: ftp://ftp3.interactivebrokers.com/usa.txt )

	for ticker in $watch; do
		if [ "$ticker" == "" ]; then
			continue
		fi

		shorts=$( echo -n "$out" | egrep "^$ticker\|" )
		shorts=$( echo -n "$shorts" | awk -F \| '{print $8}' )
		shorts=$( echo -n "$shorts" | sed 's/>//' )

		old_shorts=$( echo -n "$old_out" | egrep "^$ticker\|" )
		old_shorts=$( echo -n "$old_shorts" | awk -F \| '{print $8}' )
		old_shorts=$( echo -n "$old_shorts" | sed 's/>//' )

		if [ "$shorts" -lt "$old_shorts" ]; then
			# Available shorts decreasing
			shorts="${red}${shorts}${reset_color}"

		elif [ "$shorts" -gt "$old_shorts" ]; then
			# Indicates shorts are covering
			shorts="${green}${shorts}${reset_color}"
			echo -ne '\007'

		else
			# No change
			shorts="$shorts"
		fi

		echo -e "${ticker}\t${shorts}\t\t\t${old_shorts}"
	done

	old_out=$out

	sleep 300 # 5 minutes
done

