# Display the EMA of the average of $TICK and TICK/Q
declare lower;

input ticker_nyse = "$TICK";    # NYSE $TICK
input ticker_nsdq = "$TICK/Q";  # NASDAQ $TICK

# Get current and previous candles
def tick_nyse;
def cur_tick_nyse = hlc3(symbol=ticker_nyse);
tick_nyse = CompoundValue(1, if IsNaN(cur_tick_nyse) then tick_nyse[1] else cur_tick_nyse, cur_tick_nyse);

def tick_nsdq;
def cur_tick_nsdq = hlc3(symbol=ticker_nsdq);
tick_nsdq = CompoundValue(1, if IsNaN(cur_tick_nsdq) then tick_nsdq[1] else cur_tick_nsdq, cur_tick_nsdq);

def final_tick = ( tick_nyse + tick_nsdq ) / 2;
plot PercentChg = MovAvgExponential(final_tick, 4);
#plot PercentChg = final_tick;

plot Hist = PercentChg;
Hist.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Hist.SetLineWeight(5);
Hist.AssignValueColor(if PercentChg >= 0 then Color.GREEN else Color.RED);

plot ZeroLine = 0;
ZeroLine.SetDefaultColor(GetColor(7));

plot oversold = 3;
oversold.SetDefaultColor(GetColor(5));
plot overbought = -1;
overbought.SetDefaultColor(GetColor(5));


