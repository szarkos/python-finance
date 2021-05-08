#!/bin/bash

for i in *.csv; do
	ticker=$( head -q -n 2 $i | grep -v Symbol | awk -F , '{print $1}' )
	out=$( ./pfopt-check-history.py $ticker )

	if `echo -n $out | grep --quiet 'No Data'` ; then
		echo "$i"
		echo "$out"
	fi
done

