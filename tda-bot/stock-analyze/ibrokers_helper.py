#!/usr/bin/python3 -u

import os, sys, re
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
home = str(Path.home())

# Return the history of available shorts for a particular ticker
# Based in available shorts data from interactivebrokers
# short_history = { ticker: [{'avail_shorts': 1000, 'datetime': '2021-10-12'} , {}, ... ] }
def get_short_history(data_dir=str(home)+'/python-finance/interactivebrokers/data/', debug=False):

	short_history = {}

	# Open and process all available data files
	os.chdir(data_dir)
	file_list = filter(os.path.isfile, os.listdir(data_dir))
	file_list = [os.path.join(data_dir, f) for f in file_list]
	file_list.sort( key=lambda x: os.path.getmtime(x) )

	for fname in file_list:
		try:
			fh = open( fname, "rt" )

		except OSError as e:
			print('Error: Unable to open file ' + data_dir + '/' + str(fname) + ': ' + e, file=sys.stderr)
			sys.exit(1)

		for line in fh:
			line = line.split('|')

			if ( re.search('^#BOF', line[0]) != None ):
				# #BOF|2021.10.14|01:45:03
				date = line[1]
				date = re.sub('\.', '-', date)
				continue

			short = ''
			try:
				short = line[7]
				short = re.sub( '>', '', short )
				short = int(short)

			except:
				continue

			if ( re.search('[\>0-9]+', line[7]) == None ):
				continue

			ticker = line[0]
			if ( ticker not in short_history ):
				short_history[ticker] = []

			new_data = { 'avail_shorts': short, 'datetime': date }
			short_history[ticker].append(new_data)

		fh.close()

	return short_history

