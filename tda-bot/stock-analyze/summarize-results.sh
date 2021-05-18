
#tests="stochrsi_adx stochrsi_rsi_adx stochrsi_rsi_adx_aroonosc stochrsi_rsi_adx_dmi stochrsi_rsi_adx_dmi_aroonosc stochrsi_rsi_adx_dmi_macd stochrsi_rsi_adx_macd stochrsi_rsi_adx_macd_aroonosc stochrsi_rsi_adx_macd_dmi_aroonosc stochrsi_rsi_aroonosc stochrsi_rsi_dmi stochrsi_rsi_macd"
tests="stochrsi_adx \
	stochrsi_adx_aroonosc \
	stochrsi_adx_dmi \
	stochrsi_adx_dmi_aroonosc \
	stochrsi_adx_dmi_macd \
	stochrsi_adx_macd \
	stochrsi_adx_macd_aroonosc \
	stochrsi_adx_macd_dmi_aroonosc \
	stochrsi_aroonosc \
	stochrsi_dmi \
	stochrsi_macd"

source ./tickers.conf
tickers=$( echo -n $SMALL_MID2 | sed 's/,/ /g' )

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

