
from datetime import date, datetime, time, timedelta, timezone
from random import choice
from string import ascii_lowercase

from arrow import Arrow
from dateutil.tz import gettz
from fs.errors import ResourceNotFound
from fs.path import issamedir
from fs.zipfs import ReadZipFS
from pytest import mark, raises

from tracs.activity_types import ActivityTypes
from tracs.uid import UID
from tracs.utils import as_datetime, floor_ceil_from, floor_ceil_str, fmt, fromisoformat, fspath, ReadGzipFS, seconds_to_time, str_to_timedelta, \
	timedelta_to_iso8601, timedelta_to_str, toisoformat, unchain, unique_sorted, urlparse

def test_fmt():
	assert fmt( None ) == ''
	assert fmt( '' ) == ''

	assert fmt( 0 ) == '0'
	assert fmt( 100 ) == '100'
	assert fmt( -10 ) == '-10'

	assert fmt( 100.12345 ) == '100.1'
	assert fmt( -100.12345 ) == '-100.1'

	assert fmt( '100' ) == '100'
	assert fmt( '100.12345' ) == '100.1'

	assert fmt( 'abcd' ) == 'abcd'

	# not sure what is going on here ...
	# assert fmt( '2020-02-01T10:20:30+00:00' ) == "Feb 1, 2020, 10:20:30 AM"
	assert fmt( '2020-02-01T10:20:30+00:00' ) == "Feb 1, 2020, 10:20:30\u202fAM"
	# assert fmt( datetime( 2020, 2, 1, 10, 20, 30 ) ) == "Feb 1, 2020, 10:20:30 AM"
	assert fmt( datetime( 2020, 2, 1, 10, 20, 30 ) ) == "Feb 1, 2020, 10:20:30\u202fAM"

	assert fmt( date( 2019, 4, 25 ) ) == 'Apr 25, 2019'
	assert fmt( time( 10, 19, 25 ) ) == '10:19:25\u202fAM'
	assert fmt( time( 14, 19, 25 ) ) == '2:19:25\u202fPM'

	td = datetime( 2020, 2, 1, 10, 20, 30 ) - datetime( 2020, 2, 1, 10, 20, 33 )
	assert fmt( td ) == '3 sec'
	td = datetime( 2020, 2, 1, 10, 20, 30 ) - datetime( 2020, 2, 1, 10, 21, 33 )
	assert fmt( td ) == '63 sec'
	td = datetime( 2020, 2, 1, 10, 20, 30 ) - datetime( 2020, 2, 1, 10, 23, 33 )
	assert fmt( td ) == '3 min'
	td = datetime( 2020, 2, 1, 10, 20, 30 ) - datetime( 2020, 2, 1, 10, 30, 41 )
	assert fmt( td ) == '10 min'
	td = datetime( 2020, 2, 1, 11, 47, 30 ) - datetime( 2020, 2, 1, 10, 30, 41 )
	assert fmt( td ) == '77 min'

	assert fmt( ActivityTypes.drive ) == 'Driving'

def test_localized_fmt():
	assert fmt( 100.12345, 'de' ) == '100,1'
	assert fmt( -100.12345, 'de' ) == '-100,1'

	assert fmt( '2020-02-01T10:20:30+00:00', 'de' ) == "01.02.2020, 10:20:30"
	assert fmt( datetime( 2020, 2, 1, 10, 20, 30 ), 'de' ) == "01.02.2020, 10:20:30"

	assert fmt( date( 2019, 4, 25 ), 'de' ) == '25.04.2019'
	assert fmt( time( 10, 19, 25 ), 'de' ) == '10:19:25'
	assert fmt( time( 14, 19, 25 ), 'de' ) == '14:19:25'

def test_seconds_to_time():
	assert seconds_to_time( None ) is None
	assert seconds_to_time( '' ) is None

	assert seconds_to_time( 62 ) == time( 0, 1, 2 )
	assert seconds_to_time( 100.3 ) == time( 0, 1, 40 )
	assert seconds_to_time( 121.7 ) == time( 0, 2, 2 )

def test_fromisoformat():
	assert fromisoformat( '2020-02-01T10:20:30+00:00' ) == datetime( 2020, 2, 1, 10, 20, 30, tzinfo=timezone.utc )
	assert fromisoformat( '2020-02-01T10:20:30Z' ) == datetime( 2020, 2, 1, 10, 20, 30, tzinfo=timezone.utc )
	assert fromisoformat( datetime( 2020, 2, 1, 10, 20, 30 ) ) == datetime( 2020, 2, 1, 10, 20, 30 )
	assert fromisoformat( '10:20:30' ) == time( 10, 20, 30 )
	assert fromisoformat( time( 10, 20, 30 ) ) == time( 10, 20, 30 )
	assert fromisoformat( 'invalid' ) is None
	assert fromisoformat( None ) is None

def test_toisoformat():
	assert toisoformat( datetime( 2020, 2, 1, 10, 20, 30, tzinfo=timezone.utc ) ) == '2020-02-01T10:20:30+00:00'
	assert toisoformat( time( 10, 20, 30 ) ) == '10:20:30'
	assert toisoformat( '2020-02-01T10:20:30+00:00' ) == '2020-02-01T10:20:30+00:00'
	assert toisoformat( 'invalid' ) == 'invalid'

	assert toisoformat( timedelta( seconds=32 ) ) == '00:00:32'
	assert toisoformat( timedelta( hours=17, minutes=8, seconds=32 ) ) == '17:08:32'
	assert toisoformat( timedelta( days=1, hours=2, minutes=8, seconds=32 ) ) == '01:02:08:32'
	assert toisoformat( timedelta( hours=26, minutes=8, seconds=32 ) ) == '01:02:08:32'

def test_as_time():
	ts = 946684800 # new year 2000 UTC
	assert as_datetime( ts=ts ) == datetime( 2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc )
	assert as_datetime( ts=ts, tz=gettz() ) == datetime( 2000, 1, 1, 1, 0, 0, tzinfo=gettz() )
	assert as_datetime( ts=ts, tzstr='Europe/Berlin' ) == datetime( 2000, 1, 1, 1, 0, 0, tzinfo=gettz( 'Europe/Berlin' ) )
	assert as_datetime( ts=ts, tz=timezone.utc, tzstr='Europe/Berlin' ) == datetime( 2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc )

	ts = 946684800000 # new year 2000 UTC, millisecond precision
	assert as_datetime( ts=ts ) == datetime( 2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc )

	dt = datetime( 2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc )
	assert as_datetime( dt ) == dt
	assert as_datetime( dt, tz=gettz() ) == datetime( 2000, 1, 1, 1, 0, 0, tzinfo=gettz() )
	assert as_datetime( dt, tz=timezone.utc, tzstr='Europe/Berlin' ) == datetime( 2000, 1, 1, 1, 0, 0, tzinfo=gettz() )

	dt_iso = '2000-01-01T00:00:00+00:00'
	assert as_datetime( dtstr=dt_iso ) == dt
	assert as_datetime( dtstr=dt_iso, tz=gettz() ) == datetime( 2000, 1, 1, 1, 0, 0, tzinfo=gettz() )
	dt_iso = '2000-01-01T01:00:00+01:00'
	assert as_datetime( dtstr=dt_iso ) == datetime( 2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc )

	assert as_datetime( None ) is None
	assert as_datetime( '' ) is None

def test_timedelta_iso8601():
	assert timedelta_to_iso8601( timedelta( hours=2, minutes=38, seconds=17 ) ) == 'PT02H38M17S'
	assert timedelta_to_iso8601( timedelta( days=3, hours=2, minutes=38, seconds=17 ) ) == 'P03DT02H38M17S'

def test_timedelta_str():
	assert timedelta_to_str( timedelta( hours = 0, minutes = 0, seconds = 17 ) ) == '00:00:17'
	assert timedelta_to_str( timedelta( hours = 2, minutes = 28, seconds = 17 ) ) == '02:28:17'
	assert timedelta_to_str( timedelta( seconds = 121 ) ) == '00:02:01'
	assert timedelta_to_str( timedelta( days=3, hours = 2, minutes = 28, seconds = 17 ) ) == '03:02:28:17'
	assert timedelta_to_str( timedelta( days=12, hours = 2, minutes = 28, seconds = 17 ) ) == '12:02:28:17'

	assert str_to_timedelta( '00:00:17' ) == timedelta( hours = 0, minutes = 0, seconds = 17 )
	assert str_to_timedelta( '02:28:17' ) == timedelta( hours = 2, minutes = 28, seconds = 17 )
	assert str_to_timedelta( '03:02:28:17' ) == timedelta( days = 3, hours = 2, minutes = 28, seconds = 17 )
	assert str_to_timedelta( '12:02:28:17' ) == timedelta( days = 12, hours = 2, minutes = 28, seconds = 17 )

	# allow microseconds
	assert timedelta_to_str( timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=3 ) ) == '00:00:17.003000'
	assert timedelta_to_str( timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=303 ) ) == '00:00:17.303000'
	assert timedelta_to_str( timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=3, microseconds=4 ) ) == '00:00:17.003004'
	assert timedelta_to_str( timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=3, microseconds=430 ) ) == '00:00:17.003430'
	assert timedelta_to_str( timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=303, microseconds=430 ) ) == '00:00:17.303430'

	assert str_to_timedelta( '00:00:17.2' ) == timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=200, microseconds=0 )
	assert str_to_timedelta( '00:00:17.202' ) == timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=202, microseconds=0 )
	assert str_to_timedelta( '00:00:17.2026' ) == timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=202, microseconds=600 )
	assert str_to_timedelta( '00:00:17.111222' ) == timedelta( hours = 0, minutes = 0, seconds = 17, milliseconds=111, microseconds=222 )

def test_uri_parsing():
	result = urlparse( 'polar:1001' )
	assert result.scheme == 'polar' and result.path == '1001'

	# we might use fragment or query as resource identifier ...
	result = urlparse( 'polar:1001?1001.gpx' )
	assert result.query == '1001.gpx'

	result = urlparse( 'polar:1001#1001.gpx' )
	assert result.fragment == '1001.gpx'

	# querying we might use a shorter version, might not be unique, but in most cases having the id two times is redundant
	result = urlparse( 'polar:1001?gpx' )
	assert result.query == 'gpx'

	# a resource might also be addressed even shorter:
	result = urlparse( '1001?gpx' )
	assert result.path == '1001' and result.query == 'gpx'

def test_unchain():
	assert list( unchain( 1 ) ) == [1]
	assert list( unchain( [1] ) ) == [1]
	assert list( unchain( 1, 2 ) ) == [1, 2]
	assert list( unchain( 1, [2], 3, [4, 5] ) ) == [1, 2, 3, 4, 5]
	
	assert list( unchain( None ) ) == []
	assert list( unchain( None, [None, None], None ) ) == []

def test_unique_sorted():

	assert unique_sorted( [ 3, 1, 2, 2 ] ) == [1, 2, 3]
	assert unique_sorted( [ 't', 'r', 't', 'a' ] ) == ['a', 'r', 't']

	uids = [ UID( 'strava:100' ), UID( 'polar:100' ), UID( 'polar:100' ) ]
	assert unique_sorted( uids ) == [ UID( 'polar:100' ), UID( 'strava:100' ) ] # we can use this without key as UID supports __lt__
	assert unique_sorted( uids, key=lambda uid: uid.uid ) == [ UID( 'polar:100' ), UID( 'strava:100' ) ]

def test_floor_ceil():

	a = Arrow( 2020, 5, 13, 10, 30, 50 )

	assert floor_ceil_str( a, 'year' ) == ('2020-01-01T00:00:00+00:00', '2020-12-31T23:59:59.999999+00:00')
	assert floor_ceil_str( a, 'month' ) == ('2020-05-01T00:00:00+00:00', '2020-05-31T23:59:59.999999+00:00')
	assert floor_ceil_str( a, 'day' ) == ('2020-05-13T00:00:00+00:00', '2020-05-13T23:59:59.999999+00:00')
	assert floor_ceil_str( a, 'hour' ) == ('2020-05-13T10:00:00+00:00', '2020-05-13T10:59:59.999999+00:00')
	assert floor_ceil_str( a, 'minute' ) == ('2020-05-13T10:30:00+00:00', '2020-05-13T10:30:59.999999+00:00')
	assert floor_ceil_str( a, 'second' ) == ('2020-05-13T10:30:50+00:00', '2020-05-13T10:30:50.999999+00:00')

	assert floor_ceil_str( a, 'year', as_date=True ) == ('2020-01-01', '2020-12-31')
	assert floor_ceil_str( a, 'month', as_date=True ) == ('2020-05-01', '2020-05-31')
	assert floor_ceil_str( a, 'day', as_date=True ) == ('2020-05-13', '2020-05-13')
	assert floor_ceil_str( a, 'hour', as_date=True ) == ('2020-05-13', '2020-05-13')
	assert floor_ceil_str( a, 'minute', as_date=True ) == ('2020-05-13', '2020-05-13')
	assert floor_ceil_str( a, 'second', as_date=True ) == ('2020-05-13', '2020-05-13')

	# next 3 cases are undefined ??
	assert floor_ceil_str( a, 'year', as_time=True ) == ('00:00:00', '23:59:59')
	assert floor_ceil_str( a, 'month', as_time=True ) == ('00:00:00', '23:59:59')
	assert floor_ceil_str( a, 'day', as_time=True ) == ('00:00:00', '23:59:59')
	assert floor_ceil_str( a, 'hour', as_time=True ) == ('10:00:00', '10:59:59')
	assert floor_ceil_str( a, 'minute', as_time=True ) == ('10:30:00', '10:30:59')
	assert floor_ceil_str( a, 'second', as_time=True ) == ('10:30:50', '10:30:50')

	assert floor_ceil_from( '2020', as_str=True ) == ('2020-01-01T00:00:00+00:00', '2020-12-31T23:59:59.999999+00:00')
	assert floor_ceil_from( '2020-05', as_str=True ) == ('2020-05-01T00:00:00+00:00', '2020-05-31T23:59:59.999999+00:00')
	assert floor_ceil_from( '2020-05-13', as_str=True ) == ('2020-05-13T00:00:00+00:00', '2020-05-13T23:59:59.999999+00:00')
	assert floor_ceil_from( '10', as_str=True ) == ('0001-01-01T10:00:00+00:00', '0001-01-01T10:59:59.999999+00:00')
	assert floor_ceil_from( '10:30', as_str=True ) == ('0001-01-01T10:30:00+00:00', '0001-01-01T10:30:59.999999+00:00')
	assert floor_ceil_from( '10:30:50', as_str=True ) == ('0001-01-01T10:30:50+00:00', '0001-01-01T10:30:50.999999+00:00')

# fs

@mark.file( 'environments/default/takeouts/drive-20240825-161341.gpx.gz' )
def test_gzip_fs( path ):
	fs = ReadGzipFS( str( path ) )
	assert fs.listdir( '/' ) == [ 'drive-20240825-161341.gpx' ]
	assert fs.readtext( '/' ).startswith( '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>' )
	assert [f for p, d, f in fs.walk.walk( '/' )] == []

@mark.file( 'environments/default/takeouts' )
def test_fspath( path ):
	fs, p = fspath( path )
	assert issamedir( str( path ), fs.getsyspath( '/' ) ) and p is None

	fs, p = fspath( f'{path}/drive-20240825-160655.gpx' )
	assert issamedir( str( path ), fs.getsyspath( '/' ) ) and p == 'drive-20240825-160655.gpx'

	fs, p = fspath( f'{path}/drive-20240826-132945.zip' )
	assert isinstance( fs, ReadZipFS ) and p is None

	fs, p = fspath( f'{path}/drive-20240825-161341.gpx.gz' )
	assert isinstance( fs, ReadGzipFS ) and p is None

	random_name = ''.join( choice( ascii_lowercase ) for i in range( 32 ) )
	fs, p = fspath( f'{path}/{random_name}' )
	assert issamedir( str( path ), fs.getsyspath( '/' ) ) and p == random_name # works with non-existing files

	with raises( ResourceNotFound ):
		fspath( f'{path}/{random_name}/{random_name}' ) # ... but not with non-existing parent dirs
