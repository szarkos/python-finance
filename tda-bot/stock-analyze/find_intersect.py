#!/usr/bin/python3 -u
# Find the intersection of two arrays

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='First list of stocks (comma delimited)', required=True, type=str)
parser.add_argument("--stocks2", help='Second list of stocks (comma delimited)', required=True, type=str)
args = parser.parse_args()


def intersection( arr1=[], arr2=[] ):

	result = list( filter(lambda x: x in arr1, arr2) )
	return result


first_list = list( args.stocks.split(',') )
second_list = list( args.stocks2.split(',') )

intersect = intersection(first_list, second_list)

for i in intersect:
	print(str(i) + ' ', end='')
print()
