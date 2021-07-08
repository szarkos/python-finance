#!/bin/bash

ticker=${1-''}
if [ "$ticker" == "" ]; then
	echo "Please specify a ticker"
	exit
fi

out=$( curl --silent -u shortstock: ftp://ftp3.interactivebrokers.com/usa.txt )
shorts=$( echo -n "$out" | egrep "^$ticker\|" )

echo "$shorts"
