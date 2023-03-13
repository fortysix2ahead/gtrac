
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import timezone
from datetime import tzinfo
from difflib import SequenceMatcher
from enum import Enum
from re import match
from time import gmtime
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from babel.dates import format_datetime
from babel.dates import format_date
from babel.dates import format_time
from babel.dates import format_timedelta
from babel.numbers import format_decimal
from babel.dates import get_timezone
from click import style
from confuse import Configuration
from dateutil.parser import parse as parse_datetime
from dateutil.parser import ParserError
from dateutil.tz import gettz
from dateutil.tz import tzlocal

from .activity_types import ActivityTypes

@dataclass
class UtilityConfiguration:

	config: Configuration = field( default=None )
	locale: str = field( default='en' )
	date_format: str = field( default='medium' )
	datetime_format: str = field( default='medium' )
	time_format: str = field( default='medium' )
	timedelta_format: str = field( default='short' )

	def reconfigure( self, config: Configuration ):
		self.config = config
		self.locale = config['formats']['locale'].get() or self.locale
		self.date_format = config['formats']['date'].get() or self.date_format
		self.datetime_format = config['formats']['datetime'].get() or self.datetime_format
		self.time_format = config['formats']['time'].get() or self.time_format
		self.timedelta_format = config['formats']['timedelta'].get() or self.timedelta_format

UCFG = UtilityConfiguration()

# custom types

FunctionDict = Dict[Union[str, Tuple[str, str]], Callable]

# default formats

_DTISO = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z|[+-](?:2[0-3]|[01][0-9]):[0-5][0-9])?$'

def fmt( value, locale = None ) -> str:
	_rval = ''

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
		_rval = format_decimal( value, format='#,###.#', locale=UCFG.locale )

	if type( value ) is datetime:
		_rval = format_datetime( value, locale=UCFG.locale, format=UCFG.time_format )

	if type( value ) is date:
		_rval = format_date( value, locale=UCFG.locale, format=UCFG.time_format )

	if type( value ) is time:
		_rval = format_time( value, locale=UCFG.locale, format=UCFG.time_format )

	if type( value ) is timedelta:
		_rval = format_timedelta( value, locale=UCFG.locale, format=UCFG.timedelta_format, granularity='second', threshold=3 )
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

def unarg( key: str, *args, kwargs: Dict ) -> List[Any]:
	return [*args[0]] or value if type( value := kwargs.get( key, [] ) ) is list else [value]

# styling helpers

def blue( s: str ) -> str:
	return style( s, fg='blue' )

def red( s: str ) -> str:
	return style( s, fg='red' )
