declare lower;

def mom = close - close[1];
def V = volume;
def T = Tick_count;

plot zero = 0;
def vratio = (V / T);

def ma_length = 50;

def t_kama = MovAvgAdaptive("price"=MovAvgAdaptive("price"=MovAvgAdaptive("price"=log(vratio), "slow length"=ma_length), "slow length"=ma_length), "slow length" = ma_length);
#plot TRIX_KAMA = (t_kama - t_kama[1]) * 10000;
#plot TRIX_KAMA_SIGNAL = ExpAverage(TRIX_KAMA, 6);


####################################
# UPTICK and DOWNTICK calculation
def flat_bar    = close == open;
def green_bar   = close > open;
def red_bar     = close < open;
def up_bar      = close > close[1];
def down_bar    = close < close[1];

def current_ticks = Fundamental(FundamentalType.TICK_COUNT); 
def tick_volume = current_ticks;

def range = TrueRange(high,low,close);
def bar_height = high-low;
def bar_body = absvalue(open-close);
def almostZero = ticksize()/2;
def upticks_coeff = if flat_bar then 1/2 else      
    if green_bar then 
        (1/2 + (bar_body/bar_height)/2)
    else 
        (1/2 - (bar_body/bar_height)/2);
def downticks_coeff = 1-upticks_coeff;
def possible_upticks = tick_volume * upticks_coeff ;
def TICKS_UP = if flat_bar then floor(tick_volume/2) else floor(possible_upticks);
def TICKS_DOWN = tick_volume - TICKS_UP;

def tick_ratio;
if ( TICKS_UP[1] + TICKS_DOWN[1] ) != 0 {
    tick_ratio = ( TICKS_UP + TICKS_DOWN ) / ( TICKS_UP[1] + TICKS_DOWN[1] );
}
else {
    tick_ratio = 0;
};

#plot TICKS_DOWN2 = -TICKS_DOWN;
#TICKS_UP.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
#TICKS_DOWN2.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
#TICKS_UP.AssignValueColor(Color.GREEN);
#TICKS_DOWN2.AssignValueColor(Color.RED);

#plot v_up = (V / TICKS_UP) / (V[1] / TICKS_UP[1] );
#plot v_down = (V / TICKS_DOWN) / (V[1] / TICKS_DOWN[1]);
#plot v_total = (V / (TICKS_UP + TICKS_DOWN)) / (V[1] / (TICKS_UP[1] + TICKS_DOWN[1]));
def v_up = (TICKS_UP * V) - (TICKS_UP[1] * V[1]);
def v_down = (TICKS_DOWN * V) - (TICKS_DOWN[1] * V[1]);
#plot v_total = ((TICKS_UP + TICKS_DOWN) - (TICKS_UP[1] + TICKS_DOWN[1])) * V;
#plot tick_vol = vratio / vratio[1];
#v_up.AssignValueColor(Color.GREEN);
#v_down.AssignValueColor(Color.RED);
#v_total.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
#v_total.AssignValueColor(CreateColor(211, 211, 211));

plot v_updown_ratio = (v_up - v_down) / (v_up[1] - v_down[1]);
v_updown_ratio.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);

#AssignPriceColor(
#    if ( tick_ratio > target ) then
#        CreateColor(255, 255, 0)
#    else if mom > 0 then
#        Color.UPTICK
#    else Color.DOWNTICK );


#plot up_signal = if ( TRIX_KAMA crosses above TRIX_KAMA_SIGNAL ) then TRIX_KAMA else Double.NaN;
#plot down_signal = if ( TRIX_KAMA crosses below TRIX_KAMA_SIGNAL ) then TRIX_KAMA else Double.NaN;

#up_signal.SetDefaultColor(Color.UPTICK);
#up_signal.SetPaintingStrategy(PaintingStrategy.ARROW_UP);
#down_signal.SetDefaultColor(Color.DOWNTICK);
#down_signal.SetPaintingStrategy(PaintingStrategy.ARROW_DOWN);

#def length = 24;
#def price = hl2;
#def tr = MovAvgAdaptive("price"=MovAvgAdaptive("price"=MovAvgAdaptive("price"=log(price), "slow length"=length), "slow length"=length), "slow length" = length);
#plot TRIX = (tr - tr[1]) * 10000;


#plot long = Sum(volume * T, length) / Sum(volume, length);
#plot SMA = SimpleMovingAvg(base_volume_per_tick, ma_length);
#plot EMA = MovAvgExponential(base_volume_per_tick, ma_length*5);
def SMA = SimpleMovingAvg(vratio, ma_length);
def target = SMA * 2;

#plot VolumePerTick;
#VolumePerTick.DefineColor("Positive", Color.UPTICK);
#VolumePerTick.DefineColor("Negative", Color.DOWNTICK);
#VolumePerTick.DefineColor("Institution", CreateColor(255, 255, 0));
#VolumePerTick.AssignValueColor(
#    if mom >= 0 then
#        VolumePerTick.Color("Positive")
#    else VolumePerTick.Color("Negative"));
#
#if vratio > max {
#    VolumePerTick = max;
#}
#else if vratio < min {
#    VolumePerTick = min;
#}
#else {
#    VolumePerTick = vratio;
#};

#AssignPriceColor(
#    if ( vratio > target ) then
#        CreateColor(255, 255, 0)
#    else if mom > 0 then
#        Color.UPTICK
#    else Color.DOWNTICK );



