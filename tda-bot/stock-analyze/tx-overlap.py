#!/usr/bin/python3 -u

import os, sys, re
import time, datetime, pytz
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("algo1_ifile", help='Results file for the first algo to compare', default=None, type=str)
parser.add_argument("algo2_ifile", help='Results file for the second algo to compare', default=None, type=str)
parser.add_argument("--verbose", help='More verbose results', action="store_true")
args = parser.parse_args()

mytimezone = pytz.timezone("US/Eastern")

# Read the ledger files
algo1 = ''
algo2 = ''
try:
	with open(args.algo1_ifile, 'rt') as handle:
		algo1 = handle.read()
except Exception as e:
	print('Error opening file ' + str(args.algo1_ifile) + ': ' + str(e))
	sys.exit(1)

try:
	with open(args.algo2_ifile, 'rt') as handle:
		algo2 = handle.read()
except Exception as e:
	print('Error opening file ' + str(args.algo2_ifile) + ': ' + str(e))
	sys.exit(1)


# Add the dates of the transactions for each algo to algoN_txs
algo1_txs = []
for line in algo1.splitlines():
	if ( re.search('Warning', line) != None ):
		continue
	if ( re.search('2021\-', line) == None ):
		continue

	line = re.split('[\s\t]+', line)
	datestr = str(line[6]) + ' ' + re.sub('\..*', '', line[7])

	date = datetime.datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
	date = mytimezone.localize(date)
	algo1_txs.append(date)

algo2_txs = []
for line in algo2.splitlines():
	if ( re.search('Warning', line) != None ):
		continue
	if ( re.search('2021\-', line) == None ):
		continue

	line = re.split('[\s\t]+', line)
	datestr = str(line[6]) + ' ' + re.sub('\..*', '', line[7])

	date = datetime.datetime.strptime(datestr, '%Y-%m-%d %H:%M:%S')
	date = mytimezone.localize(date)
	algo2_txs.append(date)


def algo_compare(algo1_txs=[], algo2_txs=[]):

	if ( len(algo1_txs) == 0 or len(algo2_txs) == 0 ):
		return []

	# Compare the transactions dates from algo1 to algo2 and call out any overlaps
	overlap = []
	for idx,tx in enumerate(algo1_txs):

		# Even idx is the trade entry datetime
		if ( idx % 2 != 0 ):
			continue

		algo1_entry = algo1_txs[idx]
		algo1_exit = algo1_txs[idx+1]

		for idx2,tx2 in enumerate(algo2_txs):
			if ( idx2 % 2 != 0 ):
				continue

			algo2_entry = algo2_txs[idx2]
			algo2_exit = algo2_txs[idx2+1]

			if ( algo2_entry >= algo1_entry and algo2_entry <= algo1_exit ):
				overlap.append(algo1_entry.strftime('%Y-%m-%d %H:%M:%S'))

	return overlap


overlap = algo_compare(algo1_txs, algo2_txs)
overlap_pct = 0
if ( len(overlap) > 0 ):
	overlap_pct = round( len(overlap) / (len(algo1_txs)/2) * 100, 2 )


print('TXS Total: ' + str(int(len(algo1_txs)/2)) + ' / Overlaps: ' + str(len(overlap)) + ' (' + str(overlap_pct) + '%)' )

if ( args.verbose == True ):
	print('\n'.join(overlap))
	print('Algo1 Total Txs: ' + str(int(len(algo1_txs)/2)) )
	print('Algo2 Total Txs: ' + str(int(len(algo2_txs)/2)) )


