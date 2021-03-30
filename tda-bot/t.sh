stocks=$(cat stocks.txt)
for i in $stocks; do
	echo $i
	nohup ./tda-rsi-gobot.py $i >>$i.log.txt 2>&1 &
	disown
done
