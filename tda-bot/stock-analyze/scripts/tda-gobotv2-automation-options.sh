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
tickers="SPY,QQQ,TQQQ"

nohup ./tda-stochrsi-gobot-v2.py --stoploss --stocks=${tickers} --short --unsafe --fake --singleday \
	--decr_threshold=0.2 --incr_threshold=0.25 --exit_percent=0.4 --max_failed_txs=5 --stock_usd=20000 \
	--options_decr_threshold=5 --options_incr_threshold=2 --options_exit_percent=5 --options_usd=1000 \
	--resist_pct_dynamic --price_resistance_pct=0.25 --price_support_pct=0.25 \
	\
	--algos=algo_id:trintick_scalp_options,primary_trin,tick,use_keylevel,va_check,trin_ma_type:trima,trin_ma_period:8,options,quick_exit,quick_exit_percent:2 \
	--algos=algo_id:stochrsi_scalp_options,primary_stochrsi,tick,trin,use_keylevel,va_check,rsi_period:14,stochrsi_period:14,stochrsi_offset:0,trin_ma_type:trima,trin_ma_period:8,options,quick_exit,quick_exit_percent:2 \
	\
	--algo_valid_tickers=trintick_scalp_options:SPY,QQQ \
	--algo_valid_tickers=stochrsi_scalp_options:SPY,QQQ \
	\
	--algos=algo_id:TQQQ_trintick_scalp_options,primary_trin,tick,use_keylevel,keylevel_use_daily,va_check,support_resistance,trin_ma_type:hma,trin_ma_period:5,options,quick_exit,quick_exit_percent:2 \
	--algos=algo_id:TQQQ_stochrsi_scalp_options,primary_stochrsi,tick,trin,use_keylevel,keylevel_use_daily,va_check,support_resistance,rsi_period:14,stochrsi_period:14,stochrsi_offset:0,trin_ma_type:hma,trin_ma_period:5,options,quick_exit,quick_exit_percent:2 \
	\
	--algo_valid_tickers=TQQQ_trintick_scalp_options:TQQQ \
	--algo_valid_tickers=TQQQ_stochrsi_scalp_options:TQQQ \
	\
	--tx_log_dir=TX_LOGS_v2 1> logs/gobot-v2.log 2>&1 &

disown

#--trend_quick_exit --qe_stacked_ma_type=vidya --use_combined_exit \
#--algos=algo_id:trin_tick_options,primary_trin,tick,use_keylevel,keylevel_use_daily,keylevel_strict,va_check,options,roc_exit,roc_period:38,quick_exit,quick_exit_percent:2 \
#--algos=algo_id:stochrsi_options,primary_stochrsi,tick,trin,use_keylevel,keylevel_use_daily,keylevel_strict,va_check,rsi_period:14,stochrsi_period:14,stochrsi_offset:4,options,quick_exit_percent:10 \

#--algos=algo_id:trin_tick_options,primary_trin,tick,use_keylevel,keylevel_use_daily,keylevel_strict,va_check,options,roc_exit,roc_period:38,quick_exit,quick_exit_percent:2 \
#--algos=algo_id:trin_tick_options,primary_trin,tick,use_keylevel,keylevel_use_daily,keylevel_strict,va_check,options,near_expiration,roc_exit,roc_period:38,quick_exit_percent:10 \
