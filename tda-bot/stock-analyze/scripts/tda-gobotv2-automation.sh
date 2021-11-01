#!/bin/bash

time_wait=${1-"1"}

# This is just a small script to kick off the gobot
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/../.."

echo "CWD is `pwd`"
echo "Sleeping $time_wait seconds..."
sleep $time_wait

source ./stock-analyze/tickers.conf
tickers=$CUR_SET

nohup ./tda-stochrsi-gobot-v2.py --stoploss --stock_usd=50000 --stocks=${tickers} --short --singleday \
	--decr_threshold=2 --incr_threshold=0.5 --max_failed_txs=2 --exit_percent=1 \
	\
	--algos=algo_id:main,primary_stochrsi,stochrsi_offset:3,dmi_simple,aroonosc,adx,support_resistance,adx_threshold:6,min_daily_natr:6 \
	--algos=algo_id:main2,primary_stochrsi,stochrsi_offset:6,dmi_simple,aroonosc,adx,support_resistance,adx_threshold:6,supertrend,min_daily_natr:3 \
	\
	--rsi_high_limit=75 --rsi_low_limit=25 --stochrsi_offset=3 \
	--daily_atr_period=3 --supertrend_min_natr=2 --min_intra_natr=0.15 --min_daily_natr=1.5 \
	--aroonosc_with_macd_simple --variable_exit --lod_hod_check --use_natr_resistance \
	--weekly_ifile=stock-analyze/weekly-csv/TICKER-weekly-2019-2021.pickle \
	--daily_ifile=stock-analyze/daily-csv/TICKER-daily-2019-2021.pickle \
	--tx_log_dir=TX_LOGS_v2 1> logs/gobot-v2.log 2>&1 &

disown


# Older algos - TBD
#	--algos=primary_stochrsi,mfi,dmi_simple,aroonosc,adx,support_resistance,adx_threshold:6 \
#	--algos=primary_stochrsi,dmi_simple,aroonosc,adx,support_resistance,adx_threshold:6,stochrsi_offset:12 \
#	--algos=primary_stochrsi,mfi,aroonosc,adx,support_resistance,mfi_high_limit:95,mfi_low_limit:5,adx_threshold:20,adx_period:48 \
#	--algos=primary_stochrsi,rsi,mfi,adx,support_resistance,adx_threshold:20,mfi_high_limit:95,mfi_low_limit:5 \


# "Portfolio-based" algos - TBD
#	--algos=algo_id:stochrsi_stochmfi_chop_simple,\
#primary_stochrsi,stochmfi,chop_simple,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_chop_index,\
#primary_stochrsi,stochmfi,chop_index,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_chop_simple_mfi,\
#primary_stochrsi,stochmfi,chop_simple,mfi,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_chop_index_mfi,\
#primary_stochrsi,stochmfi,chop_index,mfi,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_macd,\
#primary_stochrsi,stochmfi,macd,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#macd_short_period:42,macd_long_period:52,macd_signal_period:5,macd_offset:0.00475,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_macd_chop_simple,\
#primary_stochrsi,stochmfi,macd,chop_simple,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#macd_short_period:42,macd_long_period:52,macd_signal_period:5,macd_offset:0.00475,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4 \
#	\
#	--algo_valid_tickers=stochrsi_stochmfi_chop_simple:LOW,C,WDC,RTX,TPR,ZM,NLOK,IR,MSFT,GIS,CRWD,WELL,VTR,TXN,GILD,CF,CAG \
#	--algo_valid_tickers=stochrsi_stochmfi_chop_index:MT,MS,PYPL,MRVL,ABNB,BX,BP,GLW,FITB,BIDU,BEN,ZM,RCL,HUN,GM,DISCA,AVTR,INTC,DDOG \
#	--algo_valid_tickers=stochrsi_stochmfi_chop_simple_mfi:MT,OKE,FITB,AIG,ADI,RCL,LOW,ZM,TPR,GIS,DIS,DBX,CAT \
#	--algo_valid_tickers=stochrsi_stochmfi_chop_index_mfi:UBER,XOM,MOS,BEN,ATVI,WFC,PYPL,MS,CFG,AAPL \
#	--algo_valid_tickers=stochrsi_stochmfi_macd:BA,FB,UNH,EXPE \
#	--algo_valid_tickers=stochrsi_stochmfi_macd_chop_simple:BA,FB,UNH,EXPE \

