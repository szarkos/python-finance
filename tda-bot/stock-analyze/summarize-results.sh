#!/bin/bash

tests="stochrsi_rsi_adx_vpt \
	stochrsi_rsi_macd_vpt \
	stochrsi_adx_vpt \
	stochrsi_adx_vpt_macd_simple \
	stochrsi_macd_vpt_dmi_simple \
	stochrsi_dmi_vpt_macd_simple \
	stochrsi_rsi_adx_macd \
	stochrsi_adx_dmi \
	stochrsi_adx_macd"

#tests="stochrsi_rsi_adx_vpt \
#stochrsi_rsi_adx_vpt_macd_simple \
#stochrsi_rsi_adx_vpt_dmi_simple \
#stochrsi_rsi_macd_vpt \
#stochrsi_rsi_macd_vpt_dmi_simple \
#stochrsi_rsi_dmi_vpt \
#stochrsi_rsi_dmi_vpt_macd_simple \
#stochrsi_adx_vpt \
#stochrsi_adx_vpt_dmi_simple \
#stochrsi_adx_vpt_macd_simple \
#stochrsi_macd_vpt \
#stochrsi_macd_vpt_dmi_simple \
#stochrsi_dmi_vpt \
#stochrsi_dmi_vpt_macd_simple \
#stochrsi_rsi_adx_dmi \
#stochrsi_rsi_adx_dmi_macd_simple \
#stochrsi_rsi_adx_macd \
#stochrsi_rsi_adx_macd_dmi_simple \
#stochrsi_adx_dmi \
#stochrsi_adx_dmi_macd_simple \
#stochrsi_adx_macd \
#stochrsi_adx_macd_dmi_simple"

#tests="stochrsi_rsi_vpt \
#stochrsi_rsi_adx_vpt \
#stochrsi_rsi_dmi_vpt \
#stochrsi_rsi_macd_vpt \
#stochrsi_rsi_aroonosc_vpt \
#stochrsi_rsi_adx_macd_vpt \
#stochrsi_vpt \
#stochrsi_adx_vpt \
#stochrsi_dmi_vpt \
#stochrsi_macd_vpt \
#stochrsi_aroonosc_vpt"

#tests="stochrsi_rsi \
#	stochrsi_rsi_adx \
#	stochrsi_rsi_dmi \
#	stochrsi_rsi_macd \
#	stochrsi_rsi_aroonosc \
#	stochrsi_rsi_adx_dmi \
#	stochrsi_rsi_adx_macd \
#	stochrsi_rsi_adx_aroonosc \
#	stochrsi_rsi_adx_dmi_macd \
#	stochrsi_rsi_adx_dmi_aroonosc \
#	stochrsi_rsi_adx_macd_aroonosc \
#	stochrsi_rsi_adx_macd_dmi_aroonosc"

#tests="stochrsi_rsi_vwap \
#	stochrsi_rsi_adx_vwap \
#	stochrsi_rsi_dmi_vwap \
#	stochrsi_rsi_macd_vwap \
#	stochrsi_rsi_aroonosc_vwap \
#	stochrsi_rsi_adx_dmi_vwap \
#	stochrsi_rsi_adx_macd_vwap \
#	stochrsi_rsi_adx_aroonosc_vwap \
#	stochrsi_rsi_adx_dmi_macd_vwap \
#	stochrsi_rsi_adx_dmi_aroonosc_vwap \
#	stochrsi_rsi_adx_macd_aroonosc_vwap \
#	stochrsi_rsi_adx_macd_dmi_aroonosc"

#tests="stochrsi_adx \
#	stochrsi_dmi \
#	stochrsi_macd \
#	stochrsi_aroonosc \
#	stochrsi_adx_dmi \
#	stochrsi_adx_macd \
#	stochrsi_adx_aroonosc \
#	stochrsi_adx_dmi_macd \
#	stochrsi_adx_dmi_aroonosc \
#	stochrsi_adx_macd_aroonosc \
#	stochrsi_adx_macd_dmi_aroonosc"

source ./tickers.conf
tickers=$( echo -n $SMALL_MID3 | sed 's/,/ /g' )

cd results

echo -n "stock,"
for i in $tests; do
	echo -n "$i,"
done

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

echo -e "\n\n"
for t in $tests; do

	echo "$t"
	cat *-${t} | grep 'gain\:' | sed 's/Average gain: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc
	cat *-${t} | grep 'loss\:' | sed 's/Average loss: //' | sed 's/ \/.*//' | sed -z 's/\n/ + /g' | perl -e '$a=<>; $a =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g; print "$a 0\n" ' | bc
	echo

done
