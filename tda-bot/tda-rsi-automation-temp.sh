
stocks=$(cat stocks.txt)
for i in $stocks; do
	echo $i
	nohup ./tda-rsi-gobot.py $i --rsi_low_limit 27 --rsi_high_limit 73 >>$i.log.txt 2>&1 &
	disown
done
