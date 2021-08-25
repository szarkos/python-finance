#!/bin/bash

results_dir=${1-'results'}
command=${2-'all'} # tx-stats, ticker-net-gain

tests=""
if [ "$tests" == "" ]; then
	tests=$(../gobot-test.py --print_scenarios)
fi

cd $results_dir

tickers=''
for i in *-stochrsi*; do
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

	# Print average gain/loss for each test type
	echo -e "\n\n"
	echo "Test,Avg Gain,Avg Loss"
	for t in $tests; do
		gain=$( cat *-${t} | grep 'Average gain\:' | sed 's/Average gain: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )
		loss=$( cat *-${t} | grep 'Average loss\:' | sed 's/Average loss: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc )
		echo "$t,$gain,$loss"
	done

	# Print the actual gains/losses from all the transactions for each test type
	echo -e "\n\n"
	echo "Test,Total Gain,Total Loss"
	for t in $tests; do

		files=''
		for f in *-${t}; do
			files="$files,$f"
		done

		echo -n "$t,"

		echo -n "$files" | perl -e '

			$fnames = <>;
			@all_txs = ();

			@f = split( /,/, $fnames );
			for $file (@f)  {
				open(FH, "<", "$file");
				@a = <FH>;
				close(FH);

				push @all_txs, @a;
			}

			$gain = 0;
			$loss = 0;
			foreach $tx ( @all_txs ) {
				if ( $tx !~ /2021/ )  {
					next;
				}

				chomp($tx);
				$tx =~ s/[\s\t]+/ /g;

				$net = $tx;
				$net =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g;

				@l = split( /\s+/, $net );
				$net = $l[1];

				if ( $l[1] =~ /\// )  {
					next;
				}

				$net =~ s/\-//;
				if ( $tx =~ /32m/ )  {
					$gain += $net;
				}
				elsif ( $tx =~ /31m/ )  {
					$loss += $net;
				}
				else {
					print "Error with tx: $net\n";
				}
			}

			printf("%.3f,%.3f\n", $gain, $loss);
		'
	done
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

