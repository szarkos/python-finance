#!/bin/bash

command=${1-""}
command=$(echo -n "$command" | tr '[:upper:]' '[:lower:]')

# This is just a small script to kick off the gobot
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/../.."

echo "CWD is `pwd`"

if [ "$command" != "force" ]; then

	# Wait until market opens to run the script
	echo "Sleeping until 06:30AM Eastern time..."
	while [ 1 ] ; do
		cur_time=$(TZ="America/New_York" date +%H:%M)
		echo "Current time is $cur_time"

		if [ "$cur_time" == "09:20" ]; then
			break
		fi
		sleep 30
	done
fi

# The list of tickers is contained in the $CUR_SET variable in tickers.conf
mkdir ./logs 2>/dev/null
source ./stock-analyze/tickers.conf
tickers=$CUR_SET
tickers="SPY,QQQ"

nohup ./tda-stochrsi-gobot-v2.py --stoploss --stocks=${tickers} --short --singleday --unsafe --fake --options_usd=1000 \
	--decr_threshold=1.25 --incr_threshold=0.5 --exit_percent=0.5 --max_failed_txs=5 --stock_usd=20000 \
	--options_decr_threshold=5 --options_incr_threshold=2 --options_exit_percent=5 --quick_exit_percent=10 --options_usd=1000 \
	--trend_quick_exit --use_combined_exit \
	--price_resistance_pct=0.25 --price_support_pct=0.25 \
	\
	--algos=algo_id:trin_tick_options,primary_trin,tick,use_keylevel,keylevel_use_daily,keylevel_strict,options,near_expiration,quick_exit_percent:10 \
	--algos=algo_id:stochrsi_options,primary_stochrsi,tick,trin,use_keylevel,keylevel_use_daily,keylevel_strict,rsi_period:14,stochrsi_period:14,stochrsi_offset:4,options,near_expiration,quick_exit_percent:10 \
	\
	--algo_valid_tickers=trin_tick_options:SPY \
	--algo_valid_tickers=stochrsi_options:SPY \
	\
	--weekly_ifile=stock-analyze/weekly-csv/TICKER-weekly-2019-2021.pickle \
	--tx_log_dir=TX_LOGS_v2 1> logs/gobot-v2.log 2>&1 &

disown

