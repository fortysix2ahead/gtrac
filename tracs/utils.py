from collections import namedtuple
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from difflib import SequenceMatcher
from enum import Enum
from functools import wraps
from gzip import open as open_gzip
from io import BytesIO
from itertools import chain
from os.path import abspath as abs_path, expanduser, expandvars, normpath
from pathlib import Path
from re import compile as rxcompile, match
from time import gmtime, perf_counter
from typing import BinaryIO, Callable, Dict, Iterable, List, Literal, Optional, Tuple, TypeVar, Union
from urllib.parse import ParseResult, ParseResultBytes, urlparse as urllibparse

from arrow import Arrow, get as getarrow
from attrs import define, field
from babel.dates import format_date, format_datetime, format_time, format_timedelta, get_timezone
from babel.numbers import format_decimal
from click import style
from dateutil.parser import parse as parse_datetime, ParserError
from dateutil.tz import gettz, tzlocal
from dynaconf import Dynaconf as Configuration
from fs.base import FS
from fs.errors import CreateFailed, ResourceNotFound, ResourceReadOnly
from fs.info import Info
from fs.osfs import OSFS
from fs.path import basename, dirname
from fs.tarfs import TarFS
from fs.zipfs import ReadZipFS
from rich import box
from rich.table import Table

from tracs.activity_types import ActivityTypes
from tracs.config import CONSOLE

T = TypeVar('T')

FsPath = namedtuple( 'FsPath', 'fs path' )

INT_COLON = rxcompile( '\d:.+' )
TIMEDELTA = rxcompile( '((?P<days>\d\d):)?(?P<hours>\d\d):(?P<minutes>\d\d):(?P<seconds>\d\d)(\.(?P<fraction>\d{1,6}))?' )

TIME_FRAMES = Literal[ 'year', 'quarter', 'month', 'week', 'day', 'hour', 'minute', 'second' ]

YEAR = rxcompile( '^(?P<year>[12]\d\d\d)$' )
YEAR_MONTH = rxcompile( '^(?P<year>[12]\d\d\d)-(?P<month>[01]\d)$' )
YEAR_MONTH_DAY = rxcompile( '^(?P<year>[12]\d\d\d)-(?P<month>[01]\d)-(?P<day>[0-3]\d)$' )
HOUR = rxcompile( '^(?P<hour>[0-1]\d|2[0-4])$' )
HOUR_MINUTE = rxcompile( '^(?P<hour>[0-1]\d|2[0-4]):(?P<minute>[0-5]\d)$' )
HOUR_MINUTE_SECOND = rxcompile( '^(?P<hour>[0-1]\d|2[0-4]):(?P<minute>[0-5]\d):(?P<second>[0-5]\d)$' )

@define
class UtilityConfiguration:

	config: Configuration = field( default=None )
	locale: str = field( default='en' )
	date_format: str = field( default='medium' )
	datetime_format: str = field( default='medium' )
	time_format: str = field( default='medium' )
	timedelta_format: str = field( default='short' )

	def reconfigure( self, config: Configuration ):
		self.config = config
		self.locale = config.formats.locale or self.locale
		self.date_format = config.formats.date or self.date_format
		self.datetime_format = config.formats.datetime or self.datetime_format
		self.time_format = config.formats.time or self.time_format
		self.timedelta_format = config.formats.timedelta or self.timedelta_format

UCFG = UtilityConfiguration()

# custom types

FunctionDict = Dict[Union[str, Tuple[str, str]], Callable]

# default formats

_DTISO = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'

def fmt( value, locale = None ) -> str:
	_rval = ''
	locale = locale if locale else UCFG.locale

	if value is None or value == '':
		_r_val = ''

	if isinstance( value, str ):
		if match( '^\d+$', value ): # format integer
			value = int( value )
		elif match( '^\d+\.\d+$', value ): # format float
			value = float( value )
		elif match( _DTISO, value ): # iso datetime
			value = datetime.fromisoformat( value )
		else:
			_rval = value

	if type( value ) is int:
		_rval = str( value )

	if type( value ) is float:
		_rval = format_decimal( value, format='#,###.#', locale=locale )

	if type( value ) is datetime:
		_rval = format_datetime( value, locale=locale, format=UCFG.time_format )

	if type( value ) is date:
		_rval = format_date( value, locale=locale, format=UCFG.time_format )

	if type( value ) is time:
		_rval = format_time( value, locale=locale, format=UCFG.time_format )

	if type( value ) is timedelta:
		_rval = format_timedelta( value, locale=locale, format=UCFG.timedelta_format, granularity='second', threshold=3 )
		#_rval = format_timedelta( value, locale=UCFG.locale, format=_timedelta_fmt, granularity='second', add_direction=True )

	if type( value ) is ActivityTypes:
		_rval = value.display_name
	elif isinstance( value, Enum ):
		_rval = value.value

	if type( value ) is list:
		_rval = ', '.join( [ fmt( e ) for e in value ] )

	return _rval

def fmtl( activity_list: List ) -> str:
	"""
	Returns a list of ids taken from the provided list of activities.

	:param activity_list: list of activities
	:return: string with a list of ids of the activities
	"""
	return f"[{', '.join( [str( a.id ) for a in activity_list or []] )}]"

def fmt_delta( dt1: datetime, dt2: datetime ) -> str:
	return f'{fmt( dt1 )} (\u00B1{fmt( dt1 - dt2 )})'

def timestring() -> str:
	return datetime.now( tz=tzlocal() ).strftime( '%y%m%d_%H%M%S' )

def as_datetime( dt: datetime = None, dtstr: str = None, ts: int = 0, tz: tzinfo = None, tzstr: str = None ) -> datetime:
	tz = gettz( tzstr ) if tzstr else tz # construct tz from tzstr
	tz = tz if tz else timezone.utc # tz wins over tzstr

	ts = ts / 1000 if ts > 4102444800 else ts # treat ts > year 2100 in milliseconds
	_dt = datetime.fromtimestamp( ts, tz ) if ts > 0 else None
	_dt = parse_datetime( dtstr ) if dtstr else _dt # iso string wins over ts
	_dt = dt if dt else _dt # dt wins over iso string
	_dt = _dt.astimezone( tz ) if _dt else None # return None if everything fails
	return _dt

def as_time( tstr: str = None ) -> time:
	_t = time.fromisoformat( tstr ) if tstr else None
	return _t

def delta( a: time, b: time ) -> timedelta:
	return datetime.combine( date.min, a ) - datetime.combine( date.min, b )

def timedelta_to_iso8601( td: timedelta ) -> str:
	s = timedelta_to_str( td )
	if s.count( ':' ) == 2:
		return f'PT{s}S'.replace( ':', 'H', 1 ).replace( ':', 'M', 1 )
	elif s.count( ':' ) == 3:
		return f'P{s}S'.replace( ':', 'DT', 1 ).replace( ':', 'H', 1 ).replace( ':', 'M', 1 )
	else:
		return s

def timedelta_to_str( td: timedelta ) -> str:
	s = str( td )
	if td.days > 0:
		days = f'{td.days}' if td.days > 9 else f'0{td.days}'
		s = s.split( ' ' )[2]
		s = f'{days}:0{s}' if INT_COLON.match( s ) else f'{days}:{s}'
	else:
		s = f'0{s}' if INT_COLON.match( s ) else s

	return s

def str_to_timedelta( s: str ) -> Optional[timedelta]:
	if m := TIMEDELTA.fullmatch( s ):
		days = int( m.groupdict().get( 'days' ) ) if m.groupdict().get( 'days' ) is not None else 0
		hours, minutes, seconds = int( m.groupdict().get( 'hours' ) ), int( m.groupdict().get( 'minutes' ) ), int( m.groupdict().get( 'seconds' ) )
		if fraction := m.groupdict().get( 'fraction' ):
			fraction = fraction.ljust( 6, '0' )
			millis, micros = int( fraction[0:3] ), int( fraction[3:] )
		else:
			millis, micros = 0, 0
		return timedelta( days=days, hours=hours, minutes=minutes, seconds=seconds, milliseconds=millis, microseconds=micros )
	else:
		return None

def seconds_to_time( time_float: float ) -> Optional[time]:
	if not isinstance( time_float, (float, int) ):
		return None
	gt = gmtime( round( time_float, 0 ) )
	return time( gt.tm_hour, gt.tm_min, gt.tm_sec )

def sum_times( times: List[time] ) -> Optional[time]:
	td = timedelta( seconds=0 )
	for t in times:
		td += timedelta( hours=t.hour, minutes=t.minute, seconds=t.second ) if t else timedelta( seconds=0 )
	return (datetime.min + td).time() if td.total_seconds() > 0 else None

def sum_timedeltas( timedeltas: List[timedelta] ) -> Optional[timedelta]:
	sum_td = timedelta( seconds=0 )
	for td in timedeltas:
		sum_td += td
	return sum_td

def to_isotime( timestr: str ) -> Optional[datetime]:
	try:
		return parse_datetime( timestr )
	except (ParserError, TypeError):
		return None

def fromtimezone( value ) -> time:
	return get_timezone( value ) if value else get_timezone()

def fromisoformat( value ) -> Optional[datetime] or Optional[time]:
	rval = None
	if type( value ) in [time, datetime]:
		rval = value
	elif type( value ) is str:
		try:
			rval = time.fromisoformat( value )
		except ValueError:
			try:
				rval = parse_datetime( value )
			except ParserError or OverflowError:
				pass
	return rval

def toisoformat( value ) -> Optional[str]:
	if type( value ) in [time, datetime]:
		return value.isoformat()
	elif type( value ) is timedelta:
		if value.days > 0:
			return (datetime.min + value - timedelta( days=1 )).strftime( '%d:%H:%M:%S' ) # hmpf ...
		else:
			return (datetime.min + value).strftime( '%H:%M:%S' )
	return value # todo: or return None?

def floor_ceil( a: Arrow, frame: TIME_FRAMES ) -> Tuple[Arrow, Arrow]:
	return a.floor( frame ), a.ceil( frame )

def floor_ceil_str( a: Arrow, frame: TIME_FRAMES, as_date: bool = False, as_time: bool = False ) -> Tuple[str, str]:
	f, c = floor_ceil( a, frame )
	if as_date:
		return f.format( fmt='YYYY-MM-DD' ), c.format( fmt='YYYY-MM-DD' )
	elif as_time:
		return f.format( fmt='HH:mm:ss' ), c.format( fmt='HH:mm:ss' )
	else:
		return f.isoformat(), c.isoformat()

# noinspection PyTypeChecker
def floor_ceil_from( s: str, as_str = False ) -> Union[Tuple[Arrow, Arrow], Tuple[str, str]]:
	if YEAR.fullmatch( s ):
		a, frame = getarrow( s ), 'year'
	elif YEAR_MONTH.fullmatch( s ):
		a, frame = getarrow( s ), 'month'
	elif YEAR_MONTH_DAY.fullmatch( s ):
		a, frame = getarrow( s ), 'day'
	elif HOUR.fullmatch( s ):
		a, frame = getarrow( s, 'HH' ), 'hour'
	elif HOUR_MINUTE.fullmatch( s ):
		a, frame = getarrow( s, 'HH:mm' ), 'minute'
	elif HOUR_MINUTE_SECOND.fullmatch( s ):
		a, frame = getarrow( s, 'HH:mm:ss' ), 'second'
	else:
		a, frame = getarrow( s ), 'year' # this should not happen

	# don't use as_date/as_time as there will be a wrong interpretation when dates/times are missing
	if as_str:
		if frame in ['year', 'month', 'day']:
			return floor_ceil_str( a, frame, as_date=False )
		elif frame in ['hour', 'minute', 'second']:
			return floor_ceil_str( a, frame, as_time=False )
		else:
			return floor_ceil_str( a, frame )
	else:
		return floor_ceil( a, frame )

def serialize( value ) -> Optional[str]:
	if type( value ) in [time, datetime]:
		return toisoformat( value )
	elif isinstance( value, Enum ):
		return value.name
	else:
		return value

def colored_diff( left: str, right: str ) -> Tuple[str, str]:
	left, right = '' if left is None else left, '' if right is None else right

	def rred( _s: str ) -> str:
		return f'[red]{_s}[/red]'

	def rblue( _s: str ) -> str:
		return f'[blue]{_s}[/blue]'

	def rgreen( _s: str ) -> str:
		return f'[green]{_s}[/green]'

	matcher = SequenceMatcher( None, left, right )
	left_colored, right_colored = '', ''
	for tag, left_from, left_to, right_from, right_to in matcher.get_opcodes():
		if tag == 'replace':
			left_colored += rred( left[left_from:left_to] )
			right_colored += rred( right[right_from:right_to] )
		elif tag == 'delete':
			left_colored += rblue( left[left_from:left_to] )
			right_colored += rblue( right[right_from:right_to] )
		elif tag == 'insert':
			left_colored += rgreen( left[left_from:left_to] )
			right_colored += rgreen( right[right_from:right_to] )
		elif tag == 'equal':
			left_colored += left[left_from:left_to]
			right_colored += right[right_from:right_to]
	return  left_colored, right_colored

def colored_diff_2( left: str, right: str ) -> Tuple[str, str]:
	left, right = '' if left is None else left, '' if right is None else right

	def rred( _s: str ) -> str:
		return f'[red]{_s}[/red]'

	matcher = SequenceMatcher( None, left, right )
	left_colored, right_colored = '', ''
	for tag, left_from, left_to, right_from, right_to in matcher.get_opcodes():
		if tag in ['replace', 'delete', 'insert' ]:
			left_colored += rred( left[left_from:left_to] )
			right_colored += rred( right[right_from:right_to] )
		elif tag == 'equal':
			left_colored += left[left_from:left_to]
			right_colored += right[right_from:right_to]
	return  left_colored, right_colored

def unique_sorted( l: Iterable[T], key: Optional = None ) -> List[T]:
	return sorted( list( set( l ) ), key=key )

def unchain( *values: Union[T, List[T]] ) -> Iterable[T]:
	return filter( lambda v: True if v is not None else False, chain( *[v if type( v ) is list else [v] for v in values] ) )

# work around for urlparse()-inconsistencies between python 3.8 and later versions
def urlparse( url ) -> ParseResult:
	url: ParseResultBytes = urllibparse( url )
	if url.scheme == '' and ':' in url.path:
		scheme, path = url.path.split( ':', maxsplit=1 )
		url = ParseResultBytes( scheme=scheme, netloc=url.netloc, path=path, params=url.params, query=url.query, fragment=url.fragment )
	return url

# fs related

class ReadGzipFS( FS ):

	def __init__( self, file: str ):
		super().__init__()
		self._file = file

	def getinfo( self, path, namespaces=None ) -> Info:
		return Info( {} ) # we might fill this later if required

	def listdir( self, path ) -> List[str]:
		return [ basename( self._file ) ]

	def makedir( self, path, permissions=None, recreate=False ):
		ResourceReadOnly( path ) # not supported

	def openbin( self, path, mode='r', buffering=-1, **options ) -> BinaryIO:
		with open_gzip( self._file, 'rb' ) as f:
			return BytesIO( f.read() )

	def remove( self, path ):
		ResourceReadOnly( path ) # not supported

	def removedir( self, path ):
		ResourceReadOnly( path ) # not supported

	def setinfo( self, path, info ):
		ResourceReadOnly( path ) # not supported

def abspath( path: Path|str ) -> str:
	return normpath( abs_path( expanduser( expandvars( str( path ) ) ) ) )

def fspath( path: Path|str ) -> Tuple[FS,str|None]:
	path = abspath( path )

	try:
		fs, file = OSFS( path ), None
	except CreateFailed:
		# failure: location might be a file
		try:
			fs, file = OSFS( dirname( path ) ), basename( path )
			if file.endswith( '.zip' ):
				fs, file = ReadZipFS( path ), None
			elif file.endswith( '.gz' ):
				fs, file = ReadGzipFS( path ), None

		except CreateFailed:
			# dirname( location ) is also not a directory -> give up
			raise ResourceNotFound( path )

	return fs, file

# styling helpers

def blue( s: str ) -> str:
	return style( s, fg='blue' )

def red( s: str ) -> str:
	return style( s, fg='red' )

# helper for measuring performance

TIMERS = {}

def timeit( fn ):
	@wraps( fn )
	def timeit_wrapper( *args, **kwargs ):
		start_time = perf_counter()
		result = fn( *args, **kwargs )
		end_time = perf_counter()

		timer_name = fn.__qualname__
		elapsed_time = end_time - start_time
		total_time = TIMERS.get( timer_name, 0.0 )
		TIMERS[timer_name] = total_time + elapsed_time

		return result

	return timeit_wrapper

def print_timers():
	table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
	for name, total_time in TIMERS.items():
		print( name, f'{total_time:.4f}s' )
	CONSOLE.print( table )
