#!/bin/bash

for result in results/*; do
	test_case=$( echo -n $result | sed 's/.*\-//' )

	declare "${test_case}_wins"=0
	declare "${test_case}_loss"=0
done


output=""
for result in results/*; do

	ticker=$( echo -n $result | sed 's/\-.*//' )
	test_case=$( echo -n $result | sed 's/.*\-//' )

	let wins=$( grep -c 32m $result )
	let loss=$( grep -c 31m $result )

	var="${test_case}_wins"
	declare -i "${test_case}_wins"=${!var}+$wins

	var="${test_case}_loss"
	declare -i "${test_case}_loss"=${!var}+$loss

	output="$output\n"$( echo -n "${ticker}: ${test_case}: wins=${wins}, losses=${loss}" )

done

set | grep '_wins'
set | grep '_loss'
