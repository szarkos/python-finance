#!/bin/bash

parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/.."

# Download new 3-month and weekly data
source ./tickers.conf

rm -f ./monthly-csv/*.csv      2>/dev/null
rm -f ./monthly-csv/*.pickle   2>/dev/null
rm -f ./weekly-csv/*.csv       2>/dev/null
rm -f ./weekly-csv/*.pickle    2>/dev/null

./download-history-data.sh $BIGLIST

# Create the .pickle files
for i in monthly-csv/*.csv; do
	./ph_csv2pickle.py $i
done

for i in weekly-csv/*.csv; do
	./ph_csv2pickle.py $i
done

