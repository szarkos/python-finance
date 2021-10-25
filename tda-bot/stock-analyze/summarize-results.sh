#!/bin/bash

results_dir=${1-'results'}
command=${2-'all'} # tx-stats, gain-loss, ticker-net-gain, daily
tests=${3-''}
stock_usd=${4-'5000'}

# This is our main working directory (typically tda-bot/stock-analyze/)
source_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

if [ "$tests" == "" ]; then
	tests=$( ${source_dir}/gobot-test.py --print_scenarios )
fi

cd $results_dir

tickers=''
for i in *-stoch*; do
	tickers="$tickers "$( echo -n $i | sed 's/\-.*//' )
done
tickers=$( echo -n $tickers | sed 's/ /\n/g' | uniq | tr '\n' ' ' )

# Transaction statistics
if [ "$command" == "all" -o "$command" == "tx-stats" ]; then

	echo -n "stock,"
	for i in $tests; do
		echo -n "$i,"
	done

	# Total successful transactions per test type
	echo
	for t in $tickers; do

		echo -n "$t,"
		wins=0
		for i in $tests; do
			wins=$( grep -e '[0-9]\-[0-9]' "${t}-${i}" | grep  -c 32m )

			echo -n "$wins,"
		done
		echo
	done

	# Total failed transactions per test type
	echo -e "\n\n"
	for t in $tickers; do

		echo -n "$t,"
		loss=0
		for i in $tests; do
			loss=$( grep -e '[0-9]\-[0-9]' "${t}-${i}" | grep  -c 31m )

			echo -n "$loss,"
		done
		echo
	done
fi


if [ "$command" == "all" -o "$command" == "gain-loss" ]; then

	# Average gain/loss for each test type
	echo -e "\n\n"
	echo "Test,Avg Gain,Avg Loss"
	for t in $tests; do
		gain=$( cat *-${t} | grep 'Average gain\:' | sed 's/Average gain: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )
		loss=$( cat *-${t} | grep 'Average loss\:' | sed 's/Average loss: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )
		echo "${t},${gain},${loss}"
	done

	# Total gain/loss for each test type
	echo
	echo "Test,Gain / Share,Loss / Share,Total Return"
	for t in $tests; do
		gain=$( cat *-${t} | grep 'Net gain\:' | sed 's/Net gain: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )
		loss=$( cat *-${t} | grep 'Net loss\:' | sed 's/Net loss: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )
		total_return=$( cat *-${t} | grep 'Total return\:' | sed 's/Total return: //' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )

		echo "${t},${gain},${loss},${total_return}"
	done

	# Total trades, win / loss ratio
	echo
	echo "Test,Total_Trades,Wins,Loss,Win Rate"
	for t in $tests; do
		win=$( cat *-${t} | egrep '(2020|2021|2022)' | grep 32m | wc -l )
		loss=$( cat *-${t} | egrep '(2020|2021|2022)' | grep 31m | wc -l )
		total=$( echo "$win + $loss" | bc )
		win_rate=$( echo "scale=2; ( $win / $total ) * 100" | bc )
		loss_rate=$( echo "scale=2; ( $loss / $total ) * 100" | bc )

		echo "${t},${total},${win},${loss},${win_rate}"
	done

	echo -e "\n"


#	# Print the actual gains/losses from all the transactions for each test type
#	echo -e "\n\n"
#	echo "Test,Total Gain,Total Loss"
#	for t in $tests; do
#
#		files=''
#		for f in *-${t}; do
#			files="$files,$f"
#		done
#
#		echo -n "$t,"
#
#		echo -n "$files" | perl -e '
#
#			$fnames = <>;
#			@all_txs = ();
#
#			@f = split( /,/, $fnames );
#			for $file (@f)  {
#				open(FH, "<", "$file");
#				@a = <FH>;
#				close(FH);
#
#				push @all_txs, @a;
#			}
#
#			$gain = 0;
#			$loss = 0;
#			foreach $tx ( @all_txs ) {
#				if ( $tx !~ /2021/ )  {
#					next;
#				}
#
#				chomp($tx);
#				$tx =~ s/[\s\t]+/ /g;
#
#				$net = $tx;
#				$net =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g;
#
#				@l = split( /\s+/, $net );
#				$net = $l[1];
#
#				if ( $l[1] =~ /\// )  {
#					next;
#				}
#
#				$net =~ s/\-//;
#				if ( $tx =~ /32m/ )  {
#					$gain += $net;
#				}
#				elsif ( $tx =~ /31m/ )  {
#					$loss += $net;
#				}
#				else {
#					print "Error with tx: $net\n";
#				}
#			}
#
#			printf("%.3f,%.3f\n", $gain, $loss);
#		'
#	done

fi


# Net gain and net loss per ticker, per test type
if [ "$command" == "all" -o "$command" == "ticker-net-gain" ]; then

	if [ "$command" == "all" ]; then
		echo -e "\n\n"
	fi

	echo -n "stock,"
	for i in $tests; do
		echo -n "${i}-NET_GAIN,${i}-NET_LOSS,${i}-TOTAL_GAIN,"
	done
	echo

	for t in $tickers; do

		echo -n "$t,"

		for tst in $tests; do
			gain=$( cat ${t}-${tst} | grep 'Net gain\:' | sed 's/Net gain: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )
			loss=$( cat ${t}-${tst} | grep 'Net loss\:' | sed 's/Net loss: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )

			echo -n "${gain},${loss},"

			gain=$( echo "$gain + ${loss}" | bc ) # We use + here because $loss is almost always preceded by a minus sign
			echo -n "${gain},"

		done
		echo
	done

fi

# Stats by sector
if [ "$command" == "all" -o "$command" == "sector" ]; then
	echo

	# Reference - tickers by sector
	# 108 Transportation
	# 129 Consumer_Durables
	# 148 Miscellaneous
	# 164 Public_Utilities
	# 180 Basic_Industries
	# 182 Energy
	# 185 Consumer_Non-Durables
	# 396 Capital_Goods
	# 618 Consumer_Services
	# 668 Technology
	# 916 Health_Care
	# 1307 Finance

	for tst in $tests; do
		echo "$tst"

		declare -A sector_fails
		declare -A sector_wins

		# Determine the wins/losses by sector
		losses_by_ticker=$( egrep '(2020|2021|2022)' *-${tst} | grep '31m' | sed 's/results\///' | sed 's/-.*//' | uniq -c | sort | sed 's/^\s*//' )
		wins_by_ticker=$( egrep '(2020|2021|2022)' *-${tst} | grep '32m' | sed 's/results\///' | sed 's/-.*//' | uniq -c | sort | sed 's/^\s*//' )

		while IFS= read -r line; do
			line=( $line )
			num_txs=$( echo "${line[0]} / 2" | bc )
			ticker=${line[1]}

			sector=$( egrep "^$ticker," "../tickers_sector.csv" | awk -F, '{print $2}' | tr ' ' '_' )
			if [ "$sector" == "" ]; then
				sector="None"
			fi

			if [[ -v sector_fails["$sector"] ]]; then
				sector_fails["$sector"]=$((${sector_fails["$sector"]}+$num_txs))
			else
				sector_fails["$sector"]=$num_txs
			fi


		done <<< "$losses_by_ticker"

		while IFS= read -r line; do
			line=( $line )
			num_txs=$( echo "${line[0]} / 2" | bc )
			ticker=${line[1]}

			sector=$( egrep "^$ticker," "../tickers_sector.csv" | awk -F, '{print $2}' | tr ' ' '_' )
			if [ "$sector" == "" ]; then
				sector="None"
			fi

			if [[ -v sector_wins["$sector"] ]]; then
				sector_wins["$sector"]=$((${sector_fails["$sector"]}+$num_txs))
			else
				sector_wins["$sector"]=$num_txs
			fi

		done <<< "$wins_by_ticker"


		# Print the results
		echo "Sector,Wins,Losses"
		all_sectors=$( echo -n "${!sector_fails[@]} ${!sector_wins[@]}" | sed 's/ /\n/g' | sort | uniq | tr '\n' ' ' )
		for key in $all_sectors; do
			if [[ ! -v sector_fails["$key"] ]]; then
				sector_fails["$key"]=0
			fi
			if [[ ! -v sector_wins["$key"] ]]; then
				sector_wins["$key"]=0
			fi

			echo "$key,${sector_wins[${key}]},${sector_fails[${key}]}"
		done

		unset sector_fails
		unset sector_wins

		echo
	done


	# Print out some reference info:
	#  - Which industries are represented in our ticker choice
	#  - Overall number of industries for nasdaq/nyse tickers

	# Assuming the same set of tickers were used for all tests, we only need to iterate through the first one
	echo '---------------------------------------------------------'
	echo 'Reference: Industry representation from our tickers'
	all_sectors=""
	tests_arr=( $tests )
	for t in *-${tests_arr[0]}; do
		ticker=$( echo -n $t | sed 's/-.*//' )
		sector=$( egrep "^$ticker," "../tickers_sector.csv" | awk -F, '{print $2}' | tr ' ' '_' )
		if [ "$sector" == "" ]; then
			sector="None"
		fi

		all_sectors="$all_sectors $sector"
	done

	echo -n "$all_sectors" | sed 's/^\s*//' | tr ' ' '\n' | sort | uniq -c | sed 's/^\s*//' | sort -g

	echo -e "\n"
	echo "Reference: Total Tickers by Sector"
	cat ../tickers_sector.csv | awk -F, '{print $2}' | sort | uniq -c | sort -g | sed 's/^\s*//'


fi


# Build a "portfolio" of best stocks for each test type
if [ "$command" == 'portfolio' ]; then

	echo
	echo "Portfolio of best trading stocks"
	echo

	# For each test, iterate across the tickers and find the stocks with most successful trades:
	#   - wins > loss
	#   - wins should be at least 6 or more (assuming 3-month backtest)
	#   - Win rate ((wins / total trades) * 100) should be at least 69%
	declare -A portfolio
	for i in $tests; do
		for t in $tickers; do
			loss=0
			wins=0
			wins=$( grep -e '[0-9]\-[0-9]' "${t}-${i}" | grep  -c 32m )
			loss=$( grep -e '[0-9]\-[0-9]' "${t}-${i}" | grep  -c 31m )

			if [ $(echo "$wins > $loss" | bc) == "1"  -a  $(echo "$wins > 6" | bc) == "1" ]; then
				win_rate=$( echo "scale=2; ($wins / ($wins + $loss)) * 100" | bc )

				if [ $(echo "$win_rate >= 69" | bc) == "1"  ]; then

					if [[ -v portfolio["$i"] ]]; then
						portfolio["$i"]="${portfolio[$i]},${wins}:${t}"
					else
						portfolio["$i"]="${wins}:${t}"
					fi
				fi
			fi

		done
	done

	for i in $tests; do
		if [[ -v portfolio["$i"] ]]; then
			tickers=$( echo -n ${portfolio["$i"]} | tr ',' '\n' | sort -nr | tr '\n' ' ' )

			echo "$i"
			for t in $tickers; do
				echo -n $t | awk -F: '{print $2}' | tr '\n' ','
			done

			echo
			for t in $tickers; do
				echo $t | awk -F: '{print $2":"$1}'
			done
			echo

		else
			echo "${i}: NONE"
		fi
	done


fi


# Daily test results
if [ "$command" == "all" -o "$command" == "daily" ]; then
	echo

	cd ${source_dir}
	./daily_results.sh "$results_dir" "$tests" "$stock_usd"

fi

