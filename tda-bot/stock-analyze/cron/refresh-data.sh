#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/.."

# Download new 3-month and weekly data
source ./tickers.conf

# 1-min, 3-months
rm -f ./monthly-1min-csv/*.csv      2>/dev/null
rm -f ./monthly-1min-csv/*.pickle   2>/dev/null
./download-history-1min.sh $BIGLIST

# Weeklies
rm -f ./weekly-csv/*.csv       2>/dev/null
rm -f ./weekly-csv/*.pickle    2>/dev/null
./download-history-weekly.sh $BIGLIST

# Create the .pickle files
for i in monthly-1min-csv/*.csv; do
	./ph_csv2pickle.py $i --augment_today
done

for i in weekly-csv/*.csv; do
	./ph_csv2pickle.py $i
done

