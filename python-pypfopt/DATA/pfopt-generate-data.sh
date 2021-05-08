#!/bin/bash

# This script runs the nasdaq_screener files through pfopt-generate-data.
# Instead of pulling the full history each time it finds the last date
#  from the previous file, adds 1-day and then pulls the data from that date.
#
# Full history will only need to be pulled if the nasdaq_screener files change.

prev_startdate=$( ls NASDAQ_BasicIndustries-AdjClose-*.csv 2>/dev/null | sed 's/NASDAQ_BasicIndustries\-AdjClose\-//' | sed 's/\.csv//' )
startdate=$( date -d "$prev_startdate 1 day" +%Y-%m-%d 2>/dev/null )

if [ "$startdate" == "" ]; then
	startdate='2013-01-01'
fi

for i in nasdaq_screener_*.csv; do

	echo "Processing $i with startdate=${startdate}..."
	./pfopt-generate-data.py "$i" "$startdate"

	outfile=$( echo -n $i | sed 's/\.csv//' | sed 's/nasdaq_screener_//' )
	oldoutfile="${outfile}-AdjClose-${prev_startdate}.csv"
	outfile="${outfile}-AdjClose-`date +%Y-%m-%d`.csv"

	cat "$oldoutfile" > tmpfile.csv
	tail -n +2 "$outfile" >> tmpfile.csv
	mv tmpfile.csv "$outfile"
	rm -f tmpfile.csv

done
