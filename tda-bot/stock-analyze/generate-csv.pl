#!/usr/bin/perl -w

# Process files created by "tda-rsi-gobot.py --analyze"

$stock = '';
$success = 0;
$fail = 0;
$avg_txs = 0;
$success_rate = 0;
$fail_rate = 0;
$avg_gain = 0;
$avg_loss = 0;
$avg_gain_per_share = 0;
$rating = '';

while (<>) {
	chomp($_);
	$_ =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g;

	if ( $_ =~ /10-day/ )  {
		$_ =~ s/Analyzing 10-day history for stock //;
		$_ =~ s/://;
		$stock = $_;
		next;
	}
	elsif ( $_ =~ /5-day/ )  {
		last;
	}
	elsif ( $_ =~ /Average txs/ ) {
		$_ =~ s/Average txs\/day: //;
		$avg_txs = $_;
		next;
	}
	elsif ( $_ =~ /Success rate/ ) {
		$_ =~ s/Success rate: //;
		$success_rate = $_;
		next;
	}
	elsif ( $_ =~ /Fail rate/ ) {
		$_ =~ s/Fail rate: //;
		$fail_rate = $_;
		next;
	}
	elsif ( $_ =~ /Average gain:/ ) {
		$_ =~ s/Average gain: //;
		$_ =~ s/ \/ share//;
		$avg_gain = $_;
		next;
	}
	elsif ( $_ =~ /Average loss/ ) {
		$_ =~ s/Average loss: //;
		$_ =~ s/ \/ share//;
		$avg_loss = $_;
		next;
	}
	elsif ( $_ =~ /Average gain per share/ ) {
		$_ =~ s/Average gain per share: //;
		$avg_gain_per_share = $_;
		next;
	}
	elsif ( $_ =~ /Stock rating/ ) {
		$_ =~ s/Stock rating: //;
		$rating = $_;
		next;
	}

	$_ =~ s/^[\s\t]+//;
	$_ =~ s/[\s\t]+$//;
	if ( $_ eq '' || $_ !~ /,/ )  {
		next;
	}

	my( $buy_price, $sell_price, $net_change) = split(/,/, $_);

	if ( $sell_price > $buy_price )  {
		$success++;
	}
	else  {
		$fail++;
	}
}

print "$stock,$success,$fail,$avg_txs,$success_rate,$fail_rate,$avg_gain,$avg_loss,$avg_gain_per_share,$rating\n";

