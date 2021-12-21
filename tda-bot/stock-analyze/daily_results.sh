#!/bin/bash

results_dir=${1-'results'}
tests=${2-''}
stock_usd=${3-'5000'}

if [ "$tests" == "" ]; then
        tests=$(./gobot-test.py --print_scenarios)
fi

cd $results_dir

tickers=''
for i in *-stoch*; do
	tickers="$tickers "$( echo -n $i | sed 's/\-.*//' )
done
tickers=$( echo -n $tickers | sed 's/ /\n/g' | uniq | tr '\n' ' ' )

for tst in $tests; do

	declare -A single_share_gain
	declare -A total_usd_gain

	declare -A single_share_loss
	declare -A total_usd_loss

	declare -A success_tx_num
	declare -A fail_tx_num

	for i in $tickers; do

		# Failed transactions
		failed_txs=$( egrep '(2020|2021|2022)' ${i}-${tst} | grep 31m | perl -e '@a=<>; foreach (@a) { chomp($_); $_ =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$_\n" } ' )
		success_txs=$( egrep '(2020|2021|2022)' ${i}-${tst} | grep 32m | perl -e '@a=<>; foreach (@a) { chomp($_); $_ =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$_\n" } ' )

		if [ "$failed_txs" != "" ]; then

			let linenum=1
			while IFS= read -r line; do

				# Even numbers are exits
				if [ $(echo "$linenum % 2" | bc) -eq 0 ]; then

					gain=$( echo -n "$line" | awk '{print $3}' )
					if  [ $(echo -n "$gain" | sed 's/\-//') == "0.0" ]; then
						linenum=$((linenum+1))
						continue
					fi

					tx_date=$( echo -n "$line" | awk '{print $12}' )
					if [[ -v fail_tx_num["$tx_date"] ]]; then
						fail_tx_num["$tx_date"]=$((${fail_tx_num["$tx_date"]}+1))
					else
						fail_tx_num["$tx_date"]=1
					fi

					# If this is a failed short, the number will be positive, prepend it with a minus sign.
					if `echo -n "$line" | awk '{print $1}' | grep --silent '*'` ; then
						gain="-${gain}"
					fi

					# Count up all the gains/losses for each date in the transaction log
					if [[ -v single_share_loss["$tx_date"] ]]; then
						single_share_loss["$tx_date"]=$( echo "${single_share_loss[$tx_date]} + $gain" | bc )
					else
						single_share_loss["$tx_date"]=$( echo "$gain" )
					fi

					if [[ -v total_usd_loss["$tx_date"] ]]; then
						total_usd_loss["$tx_date"]=$( echo "${total_usd_loss[$tx_date]} + ( $gain * $total_shares )" | bc )
					else
						total_usd_loss["$tx_date"]=$( echo "$gain * $total_shares" | bc )
					fi

				else
					cost_per_share=$( echo -n "$line" | awk '{print $1}' | sed 's/\*//' )
					total_shares=$( echo "$stock_usd / $cost_per_share" | bc )
				fi
				# End line processing

				linenum=$((linenum+1))

			done <<< "$failed_txs"

		fi

		if [ "$success_txs" != "" ]; then

			let linenum=1
			while IFS= read -r line; do

				# Even numbers are exits
				if [ $(echo "$linenum % 2" | bc) -eq 0 ]; then

					gain=$( echo -n "$line" | awk '{print $3}' | sed 's/\-//' )
					if  [ $(echo -n "$gain" | sed 's/\-//') == "0.0" ]; then
						linenum=$((linenum+1))
						continue
					fi

					tx_date=$( echo -n "$line" | awk '{print $12}' )
					if [[ -v success_tx_num["$tx_date"] ]]; then
						success_tx_num["$tx_date"]=$((${success_tx_num["$tx_date"]}+1))
					else
						success_tx_num["$tx_date"]=1
					fi

					# Count up all the gains/losses for each date in the transaction log
					if [[ -v single_share_gain["$tx_date"] ]]; then
						single_share_gain["$tx_date"]=$( echo "${single_share_gain[$tx_date]} + $gain" | bc )
					else
						single_share_gain["$tx_date"]=$( echo "$gain" )
					fi

					if [[ -v total_usd_gain["$tx_date"] ]]; then
						total_usd_gain["$tx_date"]=$( echo "${total_usd_gain[$tx_date]} + ( $gain * $total_shares )" | bc )
					else
						total_usd_gain["$tx_date"]=$( echo "$gain * $total_shares" | bc )
					fi

				else
					cost_per_share=$( echo -n "$line" | awk '{print $1}' | sed 's/\*//' )
					total_shares=$( echo "$stock_usd / $cost_per_share" | bc )
				fi
				# End line processing

				linenum=$((linenum+1))

			done <<< "$success_txs"

		fi

	done

	# Print the results
	echo "$tst"

	let wins=0
	let loss=0
	all_dates=$( echo -n "${!total_usd_gain[@]} ${!total_usd_loss[@]}" | sed 's/ /\n/g' | sort | uniq | tr '\n' ' ' )

	echo "Date,Total_Gain,Total_Loss,Net_Gain,Success_TX,Failed_TX,Total_TX"
	for key in $all_dates; do
		echo -n "${key},"

		if [[ ! -v total_usd_gain["$key"] ]]; then
			total_usd_gain["$key"]=0
		elif [[ ! -v total_usd_loss["$key"] ]]; then
			total_usd_loss["$key"]=0
		fi

		echo -n "${total_usd_gain[${key}]},"
		echo -n "${total_usd_loss[${key}]}," | sed 's/\-//'

		net_gain=$( echo "${total_usd_gain[${key}]} + ${total_usd_loss[${key}]}" | bc )
		echo -n "${net_gain},"

		if [ $(echo "$net_gain > 0" | bc) == "1"  ]; then
			wins=$((wins+1))
		fi
		if [ $(echo "$net_gain < 0" | bc) == "1" ]; then
			loss=$((loss+1))
		fi

		# Number of transactions
		if [[ ! -v success_tx_num["$key"] ]]; then
			success_tx_num["$key"]="0"
		fi
		if [[ ! -v fail_tx_num["$key"] ]]; then
			fail_tx_num["$key"]="0"
		fi
		echo -n "${success_tx_num["$key"]},"
		echo -n "${fail_tx_num["$key"]},"
		echo "${success_tx_num["$key"]} + ${fail_tx_num["$key"]}" | bc
	done

	echo

	win_pct=$(echo "scale=3; ($wins / ( $wins + $loss )) * 100" | bc -l | xargs printf %.1f )
	echo "Daily win/loss ratio: $wins / $loss (${win_pct}%)"
	echo

	success=""
	fail=""
	for key in $all_dates; do
		if [ ! "${success_tx_num[$key]}" == "0" ]; then
			success="${success},${success_tx_num[$key]} $key ($(date -d $key +'%A'))"
		fi
		if [ ! "${fail_tx_num[$key]}" == "0" ]; then
			fail="${fail},${fail_tx_num["$key"]} $key ($(date -d $key +'%A'))"
		fi
	done

	echo "Days with most successful trades: "
	echo -n "$success" | tr ',' '\n' | sort -nr

	echo
	echo "Days with most failed trades: "
	echo -n "$fail" | tr ',' '\n' | sort -nr

	echo -e "\n"

	unset single_share_gain
	unset total_usd_gain

	unset single_share_loss
	unset total_usd_loss

	unset success_tx_num
	unset fail_tx_num

done


