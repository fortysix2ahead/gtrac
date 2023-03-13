
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as datafield
from datetime import date
from datetime import datetime
from datetime import time
from enum import Enum
from logging import getLogger
from re import IGNORECASE
from re import compile as re_compile
from re import match
from sys import float_info
from sys import maxsize
from typing import Any
from typing import Callable
from typing import Tuple
from typing import cast
from typing import List
from typing import Mapping
from typing import Optional
from typing import Union

from arrow import Arrow
from arrow import now
from dateutil.tz import UTC
from tinydb.queries import Query
from tinydb.queries import QueryLike

from .activity import Activity
from .registry import Registry

log = getLogger( __name__ )

TYPES = {}
ALIASES = {}

@dataclass
class Filter( QueryLike ):

	# field to filter for
	field: Optional[Union[str, List[str]]] = datafield( default=None )

	# value which needs to match, i.e. calories = 100 matches doc['calories'] = 100
	value: Union[str, int, float, List, Tuple, time] = datafield( default=None )
	"""
	Value is considered as the parameter which is to be searched for while doing the filtering.
	It may be a str/float/int, which means a comparison is done, in case of a list several options
	might be valid when compared to the db values and a tuple, which is considered a range.
	"""

	# fragments/queries, only valid for resources
	fragment: Any = datafield( default=None )
	query: str = datafield( default=None )

	# indicator that value does not contain the exact value to match, but a regular expression
	regex: bool = datafield( default=False )
	# when true value is expected to be part of a list (opposite of value being a list from above)
	value_in_list: bool = datafield( default=False )
	# negates the filter
	negate: bool = datafield( default=False )

	# filter field (result of parsing the filter, used to store parse result)
	filter: Optional[str] = datafield( default=None, repr=False, compare=False )

	# filter expression (result of parsing the filter, used to store parse result)
	expr: Optional[str] = datafield( default=None, repr=False, compare=False )

	# callable to be executed during filter evaluation
	callable: Optional[Union[Callable, QueryLike]] = datafield( default=None, repr=False, compare=False )

	# indicator that the filter is invalid
	valid: bool = datafield( default=True, repr=False, compare=False )

	# indicator that freeze is to be skipped upon instance creation
	freeze_on_init: bool = datafield( default=True, repr=False, compare=False )

	def __post_init__( self ):
		if self.freeze_on_init:
			self.freeze()

	def __call__( self, value: Mapping ) -> bool:
		if self.callable:
			return self.callable( value )
		else:
			raise RuntimeError( f'error calling filter {self}, has the filter been frozen?' )

	# noinspection PyTypeChecker
	def freeze( self ) -> Filter:
		"""
		Freezes this filter (sets up the right callable for execution based on the filter fields) and returns self for convenience.

		:return: self
		"""
		if self.callable:
			return self # do nothing if a callable already exists

#		if not self.valid or self.field not in filter_types:
#			self.callable = invalid() # create invalid callable if flag valid is false
#			return self

		if TYPES.get( self.field ) in ['int', 'float']:
			self._freeze_number()

		elif TYPES.get( self.field ) == 'str':
			self._freeze_str()

		elif TYPES.get( self.field ) == 'ActivityTypes':
			self._freeze_enum()

		elif TYPES.get( self.field ) == 'List[str]':
			self._freeze_list()

		elif TYPES.get( self.field ) == 'datetime':
			self._freeze_datetime()

		elif TYPES.get( self.field ) == 'time':
			self._freeze_time()

		# all values/ranges are null -> check for existence of field
		if self.valid and self.value is None:
			self.callable = Query()[self.field].test( lambda v: True if v is None or v == '' or v == [] else False )

		if self.valid and self.negate:
			self.callable = ~ cast( Query, self.callable )

		return self

	def _freeze_number( self ) -> None:
		if type( self.value ) in [int, float]:
			self.callable = Query()[self.field] == self.value
		elif type( self.value ) is list:
			self.callable = Query()[self.field].test( lambda v: True if v in self.value else False )
		elif type( self.value ) == tuple:
			self.callable = Query()[self.field].test( lambda v: True if v and self.value[0] <= v <= self.value[1] else False )

	def _freeze_str( self ) -> None:
		if type( self.value ) == str:
			if self.regex:
				self.callable = Query()[self.field].matches( self.value, flags=IGNORECASE )
			else:
				self.callable = Query()[self.field].test( lambda v: True if v and self.value.lower() in v.lower() else False )
		elif type( self.value ) is list:
			pass

#		if self.value_in_list:
#			if self.regex:
#				self.callable = Query()[self.field].test( lambda values, s: any( [match( s, v ) for v in values] ), self.value )
#			else:
#				self.callable = Query()[self.field].test( lambda values, s: s in values, self.value )

	def _freeze_enum( self ) -> None:
		if self.value:
			if isinstance( self.value, Enum ):
				self.callable = Query()[self.field] == self.value
			elif type( self.value ) is str:
				self.callable = Query()[self.field].test( lambda v: True if v and v.name == self.value else False )

	def _freeze_list( self ) -> None:
		if self.value:
			if self.regex:
				regex = re_compile( self.value )
				self.callable = Query()[self.field].test( lambda v: True if any( regex.match( item ) for item in v ) else False )
			else:
				self.callable = Query()[self.field].test( lambda v: True if any( self.value.lower() in s.lower() for s in v ) else False )

	def _freeze_datetime( self ) -> None:
		if self.value and type( self.value ) is time:
			self.callable = Query()[self.field].test( lambda v: True if v.time() == self.value else False )
		elif type( self.value ) is tuple:
			if type( self.value[0] ) is datetime and type( self.value[1] ) is datetime:
				self.callable = Query()[self.field].test( lambda v: True if v and self.value[0] <= v <= self.value[1] else False )
			elif type( self.value[0] ) is time and type( self.value[1] ) is time:
				self.callable = Query()[self.field].test( lambda v: True if v and self.value[0] <= v.time() <= self.value[1] else False )

	def _freeze_time( self ) -> None:
		pass

	def is_empty( self ) -> bool:
		if not self.value and not self.sequence and not self.range_from and not self.range_to:
			return True
		else:
			return False

@dataclass
class FilterGroup( QueryLike ):

	AND: str = 'AND'
	OR: str = 'OR'

	filters: List[Filter] = datafield( default=None )
	conjunction: str = datafield( default=AND )

# prepared/predefined filters

def false() -> Filter:
	return Filter( field=None, value=False, callable=lambda m: False )

def true() -> Filter:
	return Filter( field=None, value=True, callable=lambda m: True )

def invalid() -> Filter:
	# noinspection PyUnusedLocal
	def fn( value: Mapping ) -> bool:
		raise RuntimeError( f'unable to execute a query marked as invalid' )
	return Filter( callable=fn, valid=False )

def classifier( c: str ) -> Filter:
	return Filter( 'uids', f'^{c}:\d+$', regex=True, value_in_list=True )

def raw_id( id: int ) -> Filter:
	return Filter( 'uids', f'^\w+:{id}+$', regex=True, value_in_list=True )

def uid( uid: str ) -> Filter:
	return Filter( 'uids', uid, regex=False, value_in_list=True )

def is_number( field: str ) -> Filter:
	return Filter( field, callable=lambda v: isinstance( v.get( field ), ( float, int ) ) )

# parse functions

def parse_filters( filters: Union[List[Filter, str], Filter, str] ) -> [Filter]:
	"""
	Parses a list of strings into a list of filters.

	:param filters: list of string to be parsed.
	:return: list of parsed filters
	"""
	if not filters:
		return []

	if type( filters ) is Filter:
		return [filters]

	if type( filters ) is str:
		filters = [filters]

	if type( filters ) is tuple:
		filters = list( filters )

	return [ parse( f ) for f in filters ]


# patterns for parse function

#filter_pattern = '^{negate}{field}{colon}{expr}$'.format( **{
#	'negate': '(?P<negate>\^?)',

filter_pattern = '^{field}{colon}{expr}$'.format( **{
	'field' : '(?P<field>\w+)',
	'colon' : '(?P<colon>::?)',
	'expr'  : '(?P<expr>.*)',
} )

filter_pattern2 = r'^(?P<caret>\^?)(?P<field>\w+)(?P<colon>::?)(?P<expr>[\w,-\.]+)$'
resource_pattern = r'^(?P<field>\w+):(?P<expr>\d+)(#(?P<fragment>[\w+-/]+))?$'

int_pattern = '^(?P<value>\d+)$'
int_list_pattern = '^(?P<values>(\d+,)+(\d+))$'
int_range_pattern = '^(?P<range_from>\d+)?\.\.(?P<range_to>\d+)?$'

number_pattern = '^(?P<value>\d+(\.\d+)?)$'
number_range_pattern = '^(?P<range_from>\d+(\.\d+)?)?\.\.(?P<range_to>\d+(\.\d+)?)?$'

word_pattern = '^(?P<value>[\w-]+)$'
word_quote_pattern = '^"(?P<value>.+)"$'
word_list_pattern = '^(?P<expr>(\w+,)+(\w+))$'

date_pattern = '^(?P<year>[12]\d\d\d)(-(?P<month>[01]\d))?(-(?P<day>[0-3]\d))?$'
date_from_pattern = '((?P<year_from>[12]\d\d\d)(-(?P<month_from>[01]\d))?(-(?P<day_from>[0-3]\d))?)?'
date_to_pattern = '((?P<year_to>[12]\d\d\d)(-(?P<month_to>[01]\d))?(-(?P<day_to>[0-3]\d))?)?'
date_range_pattern = '^{date_from}\.\.{date_to}$'.format( **{
	'date_from': date_from_pattern,
	'date_to': date_to_pattern,
} )
date_range_keyword = '^(?P<value>\w+)$'

time_pattern = '^(?P<hour>[0-1]\d|2[0-4]):?(?P<minute>[0-5]\d)?:?(?P<second>[0-5]\d)?$'
time_from_pattern = '(?P<hour_from>[0-1]\d|2[0-4]):?(?P<minute_from>[0-5]\d)?:?(?P<second_from>[0-5]\d)?'
time_to_pattern = '(?P<hour_to>[0-1]\d|2[0-4]):?(?P<minute_to>[0-5]\d)?:?(?P<second_to>[0-5]\d)?'
time_range_pattern = '^({time_from})?\.\.({time_to})?$'.format( **{
	'time_from': time_from_pattern,
	'time_to': time_to_pattern,
} )
time_range_keyword = '^(?P<value>\w+)$'

range_pattern = '^(?P<range_from>.*)\.\.(?P<range_to>.*)$'
list_pattern = '^(\w+,)+(\w+)$'
simple_pattern = '^(.*)$'

def parse( flt: Union[Filter, str] ) -> Filter:
	if type( flt ) is Filter:
		return flt

	# create filter instance
	f = Filter( freeze_on_init=False )

	# check for negation
	flt, f.negate = (flt[1:], True) if flt.startswith( '^' ) else (flt, False)

	# normalize filter string
	flt = normalize( flt )

	# preprocess
	flt = preprocess( flt )

	# match filter pattern and parse it
	if m := match( filter_pattern, flt ):
		f.filter, f.regex, f.expr = unpack_filter( **m.groupdict() )
		parse_expr( f.filter, f.expr, f )
	else: # no match -> set invalid
		f.valid = False

	log.debug( f'parsed filter to {f}' )

	# create and postprocess parsed filter
	postprocess( f )

	return f.freeze()

def parse_expr( filter: str, expr: str, f: Filter ) -> None:
	# get field type, depending on being an alias
	field_type = 'int' if filter in Registry.service_names() else TYPES.get( ALIASES.get( filter, filter ) )

	# select parse function

	if field_type == 'int':
		parse_function = parse_int

	elif field_type == 'float':
		parse_function = parse_number

	elif field_type in [ 'str', 'List[str]' ]:
		parse_function = parse_str

	elif field_type == 'datetime':
		# special treatment of date/time filter
		if filter == 'date':
			parse_function = parse_date
		elif filter == 'time':
			parse_function = parse_time
		else:
			parse_function = None

	elif field_type == 'ActivityTypes':
		parse_function = parse_enum

	else:
		parse_function = None

	if parse_function:
		f.value, f.valid = parse_function( filter, expr )
	else:
		f.valid = False

#	if filter in Registry.services.keys():
#		f.value, f.values, f.range_from, f.range_to, f.valid = parse_int( filter, expr )
#	else:
#		valid = False

def parse_int( field: str, expr: str ) -> Tuple:
	value, valid = None, True

	if m := match( int_pattern, expr ): # single integer
		value = int( m.groupdict().get( 'value' ) )

	elif m := match( int_list_pattern, expr ): # list of integers
		value = list( map( lambda s: int( s ), m.groupdict().get( 'values' ).split( ',' ) ) )

	elif m := match( int_range_pattern, expr ):  # range of integers
		range_from = m.groupdict().get( 'range_from' )
		range_to = m.groupdict().get( 'range_to' )
		if range_from or range_to:
			range_from = int( range_from ) if range_from else ~maxsize
			range_to = int( range_to ) if range_to else maxsize
		else:
			valid = False
		value = (range_from, range_to)

	return value, valid

def parse_number( field: str, expr: str ) -> Tuple:
	value, valid = None, True

	if m := match( number_pattern, expr ):  # single number
		value = float( m.groupdict().get( 'value' ) )

	elif m := match( number_range_pattern, expr ): # range of numbers
		range_from = m.groupdict().get( 'range_from' )
		range_to = m.groupdict().get( 'range_to' )
		if range_from or range_to:
			range_from = float( range_from ) if range_from else float_info.min
			range_to = float( range_to ) if range_to else float_info.max
		else:
			valid = False
		value = (range_from, range_to)

	return value, valid

def parse_str( field: str, expr: str ) -> Tuple:
	value, valid = None, True

	if m := match( word_pattern, expr ) or match( word_quote_pattern, expr ): # words, either standalone or quoted
		value = m.groupdict().get( 'value' )

	elif m := match( word_list_pattern, expr ): # word list, quotes are not yet supported
		value = m.groupdict().get( 'expr' ).split( ',' )

	return value, valid

def parse_enum( field: str, expr: str ) -> Tuple:
	value, valid = None, True

	if m := match( word_pattern, expr ): # words only
		value = m.groupdict().get( 'value' )

	return value, valid

def parse_date( field: str, expr: str ) -> Tuple:
	value, valid = None, True

	if m := match( date_pattern, expr ):
		year, month, day = unpack_date( **m.groupdict() )
		year, month, day = int( year ), int( month ) if month else None, int( day ) if day else None
		value = (_floor( year, month, day ), _ceil( year, month, day ))

	elif m := match( date_range_pattern, expr ):
		year_from, month_from, day_from, year_to, month_to, day_to = unpack_date_range( **m.groupdict() )
		year_from, month_from, day_from = int( year_from ) if year_from else None, int( month_from ) if month_from else None, int( day_from ) if day_from else None
		year_to, month_to, day_to = int( year_to ) if year_to else None, int( month_to ) if month_to else None, int( day_to ) if day_to else None
		value = (_floor( year_from, month_from, day_from ), _ceil( year_to, month_to, day_to ))

	elif m := match( date_range_keyword, expr ):
		value = _range_of_date_keyword( m.groupdict().get( 'value' ) )
		if value == (None, None):
			valid = False

	else:
		valid = False

	return value, valid

def parse_time( field: str, expr: str ) -> Tuple:
	value, valid = None, True

	if m := match( time_pattern, expr ):
		hour, minute, second = unpack_time( **m.groupdict() )
		hour, minute, second = int( hour ), int( minute ) if minute else 0, int( second ) if second else 0
		value = time( hour, minute, second )

	elif m := match( time_range_pattern, expr ):
		hour_from, minute_from, second_from, hour_to, minute_to, second_to = unpack_time_range( **m.groupdict() )
		hour_from, minute_from, second_from = int( hour_from ) if hour_from else 0, int( minute_from ) if minute_from else 0, int( second_from ) if second_from else 0
		hour_to, minute_to, second_to = int( hour_to ) if hour_to else 0, int( minute_to ) if minute_to else 0, int( second_to ) if second_to else 0
		range_from = time( hour_from, minute_from, second_from )
		range_to = time( hour_to, minute_to, second_to )
		value = range_from, range_to

	elif m := match( time_range_keyword, expr ):
		value = _range_of_time_keyword( m.groupdict().get( 'value' ) )
		if value == (None, None):
			valid = False

	else:
		valid = False

	return value, valid

def normalize( flt: str ) -> str:
	"""
	Normalize the filter, bringing it to the form of <field>:<expression>.

	:param flt: filter string
	:return: normalized filter string
	"""
	# integer number only
	if m := match( int_pattern, flt ):
		normalized_flt = f'id:{flt}'

	# list of integers
	elif m := match( int_list_pattern, flt ):
		normalized_flt = f'id:{flt}'

	# range of integers
	elif m := match( int_range_pattern, flt ):
		normalized_flt = f'id:{flt}'

	# service name
	elif flt in Registry.service_names():
		normalized_flt = f'service:{flt}'

	else:
		normalized_flt = flt

	if flt != normalized_flt:
		log.debug( f'normalized filter {flt} to {normalized_flt}' )

	return normalized_flt

def preprocess( flt: str ) -> str:
	"""
	Reserved for future use.

	:param flt:
	:return:
	"""

	preprocessed_flt = flt

	if flt != preprocessed_flt:
		log.debug( f'preprocessed filter {flt} to {preprocessed_flt}' )

	return preprocessed_flt

def postprocess( f: Filter ) -> None:

	if not f.valid: # do nothing when filter is already invalid
		return

	# set field according to alias

	f.field = f.filter if (f.filter in TYPES or f.filter in Registry.service_names() ) else None
	f.field = ALIASES.get( f.field, f.field ) # use existing field instead of alias ...

	if not f.field:
		f.valid = False
		return

	if TYPES.get( f.filter ) in [ 'str', 'List[str]' ]:
		if type( f.value ) is str:
			f.value = f.value.lower()
		elif type( f.value ) is list:
			f.value = list( map( lambda s: s.lower(), f.value ) )

	# allow queries for <service>:<id>
	if f.filter in Registry.services.keys() and type( f.value ) is int:  # allow queries like <service>:<id>
		f.value = f'{f.field}:{f.value}'
		f.field = 'uids'

	# service/source keys are allowed, but are not queryable directly
	if f.filter in [ 'service', 'source' ]:
		f.field = 'classifier'

	# a classifier field does not exist, it can only be queried indirectly
	if f.field == 'classifier' and f.value in Registry.services.keys():  # allow queries for classifier
		f.value = f'^{f.value}:\d+$'
		f.field = 'uids'
		f.regex = True
		f.value_in_list = True

	# filter for date is actually filter for the field time
	if f.filter == 'date':
		f.field = 'time'

# helper functions

def unpack_filter( field, colon, expr ):
	return field, True if colon == '::' else False, expr

def unpack_filter_negate( negate, field, colon, expr ):
	return True if negate == '^' else False, field, True if colon == '::' else False, expr

def unpack_list( *args ):
	return list( map( lambda s: s.replace( ',', '' ), args ) )

def unpack_range( range_from, range_to ):
	return range_from, range_to

def unpack_date( year, month, day ):
	return year, month, day

def unpack_date_range( year_from, month_from, day_from, year_to, month_to, day_to ):
	return year_from, month_from, day_from, year_to, month_to, day_to

def unpack_time( hour, minute, second ):
	return hour, minute, second

def unpack_time_range( hour_from, minute_from, second_from, hour_to, minute_to, second_to ):
	return hour_from, minute_from, second_from, hour_to, minute_to, second_to

def _floor( year: int = None, month: int = None, day: int = None ) -> Optional[datetime]:
	if day:
		return Arrow( year, month, day ).floor( 'day' ).datetime.astimezone( UTC )
	elif month:
		return Arrow( year, month, 15 ).floor( 'month' ).datetime.astimezone( UTC )
	elif year:
		return Arrow( year, 7, 15 ).floor( 'year' ).datetime.astimezone( UTC )
	else:
		return Arrow( 1900, 7, 15 ).floor( 'year' ).datetime.astimezone( UTC )

def _ceil( year = None, month = None, day = None ) -> Optional[datetime]:
	if day:
		return Arrow( year, month, day ).ceil( 'day' ).datetime.astimezone( UTC )
	elif month:
		return Arrow( year, month, 15 ).ceil( 'month' ).datetime.astimezone( UTC )
	elif year:
		return Arrow( year, 7, 15 ).ceil( 'year' ).datetime.astimezone( UTC )
	else:
		return Arrow( 2099, 7, 15 ).ceil( 'year' ).datetime.astimezone( UTC )

def _range_of_date_keyword( keyword ) -> (Optional[date], Optional[date]):
	_now = now()
	range_from, range_to = (None, None)
	if keyword == 'today':
		range_from, range_to = _now.floor( 'day' ), _now.ceil( 'day' )
	elif keyword == 'thisweek':
		range_from, range_to = _now.floor( 'week' ), _now.ceil( 'week' )
	elif keyword == 'thismonth':
		range_from, range_to = _now.floor( 'month' ), _now.ceil( 'month' )
	elif keyword == 'thisquarter':
		range_from, range_to = _now.floor( 'quarter' ), _now.ceil( 'quarter' )
	elif keyword == 'thisyear':
		range_from, range_to = _now.floor( 'year' ), _now.ceil( 'year' )
	elif keyword == 'yesterday':
		_now = _now.shift( days=-1 )
		range_from, range_to = _now.floor( 'day' ), _now.ceil( 'day' )
	elif keyword == 'last7days':
		range_from, range_to = _now.shift( days=-6 ).floor( 'day' ), _now.ceil( 'day' )
	elif keyword == 'last30days':
		range_from, range_to = _now.shift( days=-29 ).floor( 'day' ), _now.ceil( 'day' )
	elif keyword == 'last60days':
		range_from, range_to = _now.shift( days=-59 ).floor( 'day' ), _now.ceil( 'day' )
	elif keyword == 'last90days':
		range_from, range_to = _now.shift( days=-89 ).floor( 'day' ), _now.ceil( 'day' )
	elif keyword == 'lastweek':
		_now = _now.shift( weeks=-1 )
		range_from, range_to = _now.floor( 'week' ), _now.ceil( 'week' )
	elif keyword == 'lastmonth':
		_now = _now.shift( months=-1 )
		range_from, range_to = _now.floor( 'month' ), _now.ceil( 'month' )
	elif keyword == 'lastquarter':
		_now = _now.shift( months=-3 )
		range_from, range_to = _now.floor( 'quarter' ), _now.ceil( 'quarter' )
	elif keyword == 'lastyear':
		_now = _now.shift( years=-1 )
		range_from, range_to = _now.floor( 'year' ), _now.ceil( 'year' )

	return range_from.datetime, range_to.datetime

def _range_of_time_keyword( keyword ) -> (Optional[time], Optional[time]):
	range_from, range_to = (None, None)

	if keyword == 'morning':
		range_from, range_to = time( 6 ), time( 11 )
	elif keyword == 'noon':
		range_from, range_to = time( 11 ), time( 13 )
	elif keyword == 'afternoon':
		range_from, range_to = time( 13 ), time( 18 )
	elif keyword == 'evening':
		range_from, range_to = time( 18 ), time( 22 )
	elif keyword == 'night':
		range_from, range_to = time( 22 ), time( 6 )

	return range_from, range_to
