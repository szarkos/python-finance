#!/usr/bin/perl -w

use Mail::Message;
use HTML::Strip;
use Fcntl;

chdir "$ENV{HOME}";

my $debug = 1;
my $logfile = '/home/steve/python-finance/stonk-mailparse/stonk-mailparse.log';
my $tdagobot = '/home/steve/python-finance/tda-bot/tda-gobot.py';

my $stock_usd = 1000;
if ( defined($ARGV[0]) && $ARGV[0] =~ /^[+-]?(?=\.?\d)\d*\.?\d*(?:e[+-]?\d+)?\z/i )  {
	$stock_usd = $ARGV[0];
}
else {
	do_log('Warning: using $1000USD for the stock investment value');
}

my $msg_obj = Mail::Message->read(\*STDIN);
my $body = $msg_obj->body->decoded;

my $obj = HTML::Strip->new();
my $clean_body = $obj->parse( $body );
$clean_body =~ s/[\r\n]/ /g;
$obj->eof;

# For Deadnsyde we are only interested in the $100 subscription emails
#if ( $clean_body =~ /Deadnsyde/i && $clean_body !~ /\$100/ )  {
if ( $clean_body =~ /Deadnsyde/i && $clean_body =~ /99C Members/i )  {
	if ( $debug == 1 )  {
		do_log('Ignoring the 99C members email');
	}
	exit(0);
}

# Check email for tickers
my %ignore = ( 	"AM"		=> 1,
		"PM"		=> 1,
		"PERL"		=> 1,
		"TEXT"		=> 1,
		"MIME"		=> 1,
		"BUT"		=> 1,
		"CEO"		=> 1,
		"CIO"		=> 1,
		"CTO"		=> 1,
		"CFO"		=> 1,
		"VR"		=> 1,
		"LLC"		=> 1,
		"FDA"		=> 1,
		"CA"		=> 1,
		"LOT"		=> 1,
		"ETF"		=> 1,
		"DOD"		=> 1,
		"LOT"		=> 1,
		"NASA"		=> 1,
		"USA"		=> 1,
		"EV"		=> 1,
		"DD"		=> 1,
		"NFT"		=> 1,
		"RE"		=> 1,
		"FYI"		=> 1,
		"BTW"		=> 1,
		"NOT"		=> 1,
		"INVESTED"	=> 1
);
my @tickers = ();
my $ticker = "";

while ( $clean_body =~ /[\s\t\.,\(]+[A-Z]{2,6}([.-])?([A-Z]{3,6})?[\s\t,.\)]?/g )  {
	$ticker = "$&";
	$ticker =~ s/[\s\t]//g;
	$ticker =~ s/\.$//;
	$ticker =~ s/^\.//;
	$ticker =~ s/\-$//;
	$ticker =~ s/,//g;
	$ticker =~ s/[\(\)]//g;
	$ticker =~ s/\.//g if ( $ticker =~ /([A-Z]+\.){2,}/ ); # Fix A.B.C.D

	next if ( exists($ignore{$ticker}) );
	push( @tickers, $ticker );
}
while ( $clean_body =~ /[\s\t]*([A-Z][\s\t\.]{1,}){3,}/g )  {
	$ticker = "$&";
	$ticker =~ s/[\s\t]//g;
	$ticker =~ s/\.//g if ( $ticker =~ /([A-Z]+\.){2,}/ );

	next if ( exists($ignore{$ticker}) );
	push( @tickers, $ticker );
}


# Remove duplicates
@tickers = uniq( @tickers );

# Check if there are normal dictionary words in here
#@tickers = check_dict( @tickers );

if ( scalar @tickers == 0 )  {
	# We didn't find any tickers - maybe a bug?
	do_log( "Error: no valid tickers found" );
#	send_email( 'stonk-mailparse :  Error', 'We did not find any tickers in the latest email. Maybe a bug?' );
}

if ( $debug == 1 )  {
	do_log("DEBUG: @tickers");
}

foreach $stock ( @tickers )  {
	system( "$tdagobot", '--checkticker', "$stock" );
	if ( $? != 0 )  {
		do_log("Found ticker ${stock}, but tda-gobot did not validate");
		next;
	}

	do_log( "Valid ticker found ($stock), running: ./tda-gobot.py --notmarketclosed $stock $stock_usd" );
	system( 'cd ${HOME}/python-finance/tda-bot/ && nohup ' . "$tdagobot" . ' --notmarketclosed ' . " $stock $stock_usd " . '1>>log.txt 2>&1 &' );
}



########################################################
sub check_dict  {
	my @array = @_;
	my @return = ();

	foreach ( @array )  {
		system( 'grep -i --silent \'^' . $_ . '$\' /usr/share/dict/*' );
		if ( $? != 0 )  {
			push( @return, $_ ); 
		}
	}

	return @return;
}


sub uniq  {
	my %seen;
	return grep { !$seen{$_}++ } @_;
}


sub send_email  {

	my $subject = "$_[0]";
	my $mesg = "$_[1]";

	# 4257366361@vtext.com
	system( 'echo ' . $mesg . ' | mail --return-address=steve@sentry.net --subject "' . $subject . '" steve@sentry.net' );

	return 0;
}


sub do_log {
	my $message = "$_[0]";
	my $fh = '';

	open( $fh, '+>>', "$logfile" );
	flock( $fh, 2 );

	print $fh localtime() . ": $message\n";

	flock( $fh, 8 );
	close( $fh );

	return 0;
}

