#!/bin/bash

red='\033[0;31m'
green='\033[0;32m'
reset_color='\033[0m'


out=$( curl --silent -u shortstock: ftp://ftp3.interactivebrokers.com/usa.txt )
watch=$( cat ./watchlist.txt )

for ticker in $watch; do
	orig_shorts=$( echo -n "$out" | egrep "^$ticker\|" )
	if [ "$orig_shorts" == "" ]; then
		declare "${ticker}_shorts"=0
	else
		orig_shorts=$( echo -n "$orig_shorts" | awk -F \| '{print $8}' )
		orig_shorts=$( echo -n "$orig_shorts" | sed 's/>//' )
		declare "${ticker}_shorts"=$orig_shorts
	fi

	declare "${ticker}_trigger"=0
done

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

		old_shorts="${ticker}_shorts"
		trigger="${ticker}_trigger"

		shorts=$( echo -n "$out" | egrep "^$ticker\|" )
		if [ "$shorts" == "" ]; then
			shorts='N/A'
		else
			shorts=$( echo -n "$shorts" | awk -F \| '{print $8}' )
			shorts=$( echo -n "$shorts" | sed 's/>//' )

			if [ "$shorts" -lt "${!old_shorts}" ]; then
				# Available shorts decreasing
				shorts="${red}${shorts}${reset_color}"
				declare "${ticker}_trigger"=0

			elif [ "$shorts" -gt "${!old_shorts}" ]; then
				# Indicates shorts are covering
				shorts="${green}${shorts}${reset_color}"

				if [ "${!trigger}" -eq 0 ]; then
					declare "${ticker}_trigger"=1
					echo -ne '\007'
				fi

			else
				# No change
				shorts="$shorts"
			fi
		fi

		echo -e "${ticker}\t${shorts}\t\t\t${!old_shorts}"
	done

	sleep 180 # 5 minutes
done

