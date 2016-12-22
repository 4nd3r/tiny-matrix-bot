#!/usr/bin/php
<?php

$dicts = array
(
	'ss' => 'http://www.eki.ee/dict/ekss/index.cgi?Q=%s&C01=1&C02=1&C03=1',
	'qs' => 'http://www.eki.ee/dict/qs/index.cgi?Q=%s&C01=1&C02=1',
);

define( 'EKI_LENGTH', 300 );
define( 'EKI_ROWS',   3 );

if ( $argc < 3 )
	exit( "eki <sõnastik> <sõna(d)>\n" );

$dict = $argv[ 1 ];

if ( ! isset( $dicts[ $dict ] ) )
	exit( "Tundmatu sõnastik.\n" );

unset( $argv[ 0 ] );
unset( $argv[ 1 ] );

$str = '';
foreach ( $argv as $arg )
	$str .= $arg . ' ';

$str  = urlencode( trim( $str ) );
$url  = sprintf( $dicts[ $dict ], $str );
$html = file_get_contents( $url );

$dom = new DOMDocument;
@$dom->loadHTML( $html ); // UTF-suutropp
$xpath = new DOMXpath( $dom );

$results = $xpath->query( '//div[contains(@class,"tervikart")]' );
$counter = 0;

foreach ( $results as $result )
{
	foreach ( $result->childNodes as $node )
	{
		$counter++;

		$line = trim( $node->nodeValue );

		if ( mb_strlen( $line ) >= EKI_LENGTH )
			$line = mb_substr( $line, 0, EKI_LENGTH - 3 ) . '...';

		echo $line . "\n";

		if ( $counter >= EKI_ROWS )
			break;
	}

	if ( $counter >= EKI_ROWS )
		break;
}

if ( $counter > 0 )
	echo $url . "\n";
else
	echo "Ei ole sellist sõna!\n";
