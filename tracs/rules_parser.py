
from __future__ import annotations

from datetime import datetime
from datetime import time
from decimal import Decimal
from decimal import InvalidOperation
from logging import getLogger
from re import match
from sys import maxsize
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Tuple
from typing import Type

from arrow import Arrow
from arrow import get as getarrow
from arrow import utcnow as now
from dateutil.tz import UTC
from rule_engine import Context
from rule_engine import resolve_attribute
from rule_engine import Rule as DefaultRule
from rule_engine import RuleSyntaxError

from tracs.rules import Rule
from tracs.rules import NumberEqRule

log = getLogger( __name__ )

INT_PATTERN = '^(?P<value>\d+)$'
INT_LIST_PATTERN = '^(?P<values>(\d+,)+(\d+))$'
INT_RANGE_PATTERN = '^(?P<range_from>\d+)?\.\.(?P<range_to>\d+)?$'

NUMBER_PATTERN = '^(?P<value>\d+(\.\d+)?)$'

QUOTED_STRING_PATTERN = '^"(?P<value>.*)"$'

KEYWORD_PATTERN = '^[a-zA-Z][\w-]*$'

RANGE_PATTERN = '^(?P<range_from>\d[\d\.\:-]+)?(\.\.)(?P<range_to>\d[\d\.\:-]+)?$'

DATE_PATTERN = '^(?P<year>[12]\d\d\d)-(?P<month>[01]\d)-(?P<day>[0-3]\d)$'
DATE_YEAR_PATTERN = '^(?P<year>[12]\d\d\d)$'
DATE_YEAR_MONTH_PATTERN = '^(?P<year>[12]\d\d\d)-(?P<month>[01]\d)$'
DATE_YEAR_MONTH_DAY_PATTERN = DATE_PATTERN

FUZZY_DATE_PATTERN = '^(?P<year>[12]\d\d\d)(-(?P<month>[01]\d))?(-(?P<day>[0-3]\d))?$'
TIME_PATTERN = '^(?P<hour>[0-1]\d|2[0-4]):(?P<minute>[0-5]\d):(?P<second>[0-5]\d)$'

SHORT_RULE_PATTERN = r'^(\w+)(:|=)([\w\"\.].+)$' # short version: id=10 or id:10 for convenience, value must begin with alphanum or "
RULE_PATTERN = '^(\w+)(==|!=|=~|!~|>=|<=|>|<|=|:)([\w\"\.].+)$'

RULES: Dict[str, Type[Rule]] = {
	'id': NumberEqRule
}

# mapping of keywords to normalized expressions
# this enables operations like 'list thisyear'
KEYWORDS: Dict[str, Callable] = {
	# date related keywords
	'last7days': lambda s: f'time >= {floor( now().shift( days=-6 ), "day" )} and time <= {ceil( now(), "day" )}',
	'last14days': lambda s: f'time >= {floor( now().shift( days=-13 ), "day" )} and time <= {ceil( now(), "day" )}',
	'last30days': lambda s: f'time >= {floor( now().shift( days=-29 ), "day" )} and time <= {ceil( now(), "day" )}',
	'last60days': lambda s: f'time >= {floor( now().shift( days=-59 ), "day" )} and time <= {ceil( now(), "day" )}',
	'last90days': lambda s: f'time >= {floor( now().shift( days=-89 ), "day" )} and time <= {ceil( now(), "day" )}',
	'today': lambda s: f'time >= {floor( now(), "day" )} and time <= {ceil( now(), "day" )}',
	'lastweek': lambda s: f'time >= {floor( now().shift( weeks=-1 ), "week" )} and time <= {ceil( now().shift( weeks=-1 ), "week" )}',
	'thisweek': lambda s: f'time >= {floor( now(), "week" )} and time <= {ceil( now(), "week" )}',
	'lastmonth': lambda s: f'time >= {floor( now().shift( months=-1 ), "month" )} and time <= {ceil( now().shift( months=-1 ), "month" )}',
	'thismonth': lambda s: f'time >= {floor( now(), "month" )} and time <= {ceil( now(), "month" )}',
	'lastquarter': lambda s: f'time >= {floor( now().shift( months=-3 ), "quarter" )} and time <= {ceil( now().shift( months=-3 ), "quarter" )}',
	'thisquarter': lambda s: f'time >= {floor( now(), "quarter" )} and time <= {ceil( now(), "quarter" )}',
	'lastyear': lambda s: f'time >= {floor( now().shift( years=-1 ), "year" )} and time <= {ceil( now().shift( years=-1 ), "year" )}',
	'thisyear': lambda s: f'time >= {floor( now(), "year" )} and time <= {ceil( now(), "year" )}',
	# todo: this needs to be detected automatically
	'bikecitizens': lambda s: f'"bikecitizens" in __classifiers__',
	'local': lambda s: f'"local" in __classifiers__',
	'polar': lambda s: f'"polar" in __classifiers__',
	'strava': lambda s: f'"strava" in __classifiers__',
	'waze': lambda s: f'"waze" in __classifiers__',
}

# normalizers transform a field/value pair into a valid normalized expression
# this enables operations like 'list classifier:polar' where ':' does not evaluate to '=='
NORMALIZERS: Dict[str, Callable] = {
	'classifier': lambda s: f'"{s}" in __classifiers__',
	'service': lambda s: f'"{s}" in __classifiers__',
	'source': lambda s: f'"{s}" in __classifiers__',
}

# custom resolvers, needed to access "virtual fields" which do not exist
# the key represents the name of the virtual field, the value is a function which calculates the actual value
RESOLVERS: Dict[str, Callable] = {
	# date/time fields
	'weekday': lambda t, n: t.time.day, # day attribute of datetime objects
	'day': lambda t, n: t.time.day, # day attribute of datetime objects
	'month': lambda t, n: t.time.month, # month attribute of datetime objects
	'year': lambda t, n: t.time.year, # year attribute of datetime objects
	'date': lambda t, n: t.time.date(), # date
	# activity type
	'type': lambda t, n: t.type.value if t.type else None,
	# internal helper attributes, which are not intended to be used directly
	'__classifiers__': lambda t, n: list( map( lambda s: s.split( ':', 1 )[0], t.uids ) ), # virtual attribute of uids
	'__date__': lambda t, n: t.time.date(), # date
	'__time__': lambda t, n: t.time.time(), # time
}

# type hints to be able to parse certain string correctly (i.e. 2022 as date, not as int)
RESOLVER_TYPES: Dict[str, Type] = {
	'date': datetime,
	'time': time,
}

def resolve_custom_attribute( thing: Any, name: str ):
	return RESOLVERS[name]( thing, name ) if name in RESOLVERS.keys() else resolve_attribute( thing, name )

# CONTEXT = Context( default_value=None, resolver=resolve_custom_attribute )
CONTEXT = Context( resolver=resolve_custom_attribute )

# predefined rules

# rules parser

def parse_rules( *rules: str ) -> List[DefaultRule]:
	return [parse_rule( r ) for r in rules]

def parse_rule( rule: str ) -> DefaultRule:

	rule: str = normalize( rule ) # normalize rule, used for preprocessing special cases
	rule: str = preprocess( rule ) # preprocess, not used at the moment
	rule: DefaultRule = process( rule )
	rule: Rule = postprocess( rule ) # create and postprocess parsed rule

	return rule

def normalize( rule: str ) -> str:

	normalized_rule = None

	if match( INT_PATTERN, rule ): # integer number only
		normalized_rule = f'id == {rule}'

	elif match( KEYWORD_PATTERN, rule ):  # keywords
		if rule in KEYWORDS:
			normalized_rule = KEYWORDS[rule]( rule )
		else:
			raise RuleSyntaxError( f'syntax error: unsupported keyword "{rule}"' )

	elif m := match( RULE_PATTERN, rule ): #
		left, op, right = m.groups()
		if op == '=':
			if match( NUMBER_PATTERN, right ) or match( QUOTED_STRING_PATTERN, right ):
				normalized_rule = f'{left} == {right}'
			elif match( DATE_PATTERN, right ) and RESOLVER_TYPES.get( left ) is datetime:
				normalized_rule = f'{left} == d"{right}"'
			elif match( TIME_PATTERN, right ) and RESOLVER_TYPES.get( left ) is time:
				normalized_rule = f'{left} == t"{right}"'
			else:
				normalized_rule = f'{left} == "{right}"'

		elif op == ':':
			if left in NORMALIZERS:
				normalized_rule = NORMALIZERS[left]( right )

			elif match( NUMBER_PATTERN, right ):
				if RESOLVER_TYPES.get( left ) is datetime: # years are caught by this regex already ...
					normalized_rule = f'{left} >= d"{parse_floor_str( right )}" and {left} <= d"{parse_ceil_str( right )}"'
				else:
					normalized_rule = f'{left} == {right}'

			elif match (QUOTED_STRING_PATTERN, right):
				normalized_rule = f'{left} != null and {right.lower()} in {left}.as_lower'

			elif match( DATE_YEAR_MONTH_PATTERN, right ) and RESOLVER_TYPES.get( left ) is datetime:
				normalized_rule = f'{left} >= d"{parse_floor_str( right )}" and {left} <= d"{parse_ceil_str( right )}"'

			elif match( DATE_YEAR_MONTH_DAY_PATTERN, right ) and RESOLVER_TYPES.get( left ) is datetime:
				normalized_rule = f'{left} >= d"{parse_floor_str( right )}" and {left} <= d"{parse_ceil_str( right )}"'

			elif match( RANGE_PATTERN, right ):
				if RESOLVER_TYPES.get( left ) is datetime:
					range_from, range_to = parse_date_range_as_str( right )
					normalized_rule = f'{left} >= d"{range_from}" and {left} <= d"{range_to}"'
				else:
					range_from, range_to = parse_number_range( right )
					normalized_rule = f'{left} >= {range_from} and {left} <= {range_to}'

			else:
				normalized_rule = f'{left} != null and "{right.lower()}" in {left}.as_lower'

		else:
			normalized_rule = f'{left} {op} {right}'

	if not normalized_rule:
		raise RuleSyntaxError( f'syntax error in expression "{rule}"' )

	log.debug( f'normalized rule {rule} to {normalized_rule}' )

	return normalized_rule

def preprocess( rule: str ) -> str:
	"""
	Reserved for future use, does nothing at the moment.

	:param rule: rule string to preprocess
	:return: preprocessed rule
	"""
	preprocessed_rule = rule

	if rule != preprocessed_rule:
		log.debug( f'preprocessed rule {rule} to {preprocessed_rule}' )

	return preprocessed_rule

def process( rule: str ) -> Rule:
	return DefaultRule( rule, CONTEXT )

	if m := match( RULE_PATTERN, rule ):
		return process_expr( rule, *m.groups() )
	else:
		raise RuntimeError( f'unable to parse rule {rule}' )

def process_expr( rule: str, left: str, op: str, right: str ) -> DefaultRule:
	pass
#	if left not in RULES.keys():
#		raise RuntimeError( f'unknown/unsupported query field {left}' )

#	if op not in RULES.get( left ).compatible_ops:
#		raise RuntimeError( f'unknown/unsupported operator "{op}" for query field {left}' )


	# rule = create_rule( left, op, right )
	# return rule

def create_rule( left: str, op: str, right: str ) -> Rule:
	return RULES.get( left )( field=left, operator=op, value=right )

def postprocess( rule: DefaultRule ) -> DefaultRule:

	postprocessed_rule = rule

	if rule != postprocessed_rule:
		log.debug( f'postprocessed rule {rule} to {postprocessed_rule}' )

	return postprocessed_rule

# helper

def parse_number_range( s: str ) -> Tuple[str, str]:
	left, right = s.split( '..', maxsplit=1 )
	try:
		range_from = Decimal( left )
	except( TypeError, InvalidOperation ):
		range_from = Decimal( ~maxsize )

	try:
		range_to = Decimal( right )
	except( TypeError, InvalidOperation ):
		range_to = Decimal( maxsize )

	return str( range_from ), str( range_to )

def parse_date_range_as_str( r: str ) -> Tuple[str, str]:
	range_from, range_to = parse_date_range( r )
	return range_from.strftime( '%Y-%m-%d' ), range_to.strftime( '%Y-%m-%d' )

def parse_date_range( r: str ) -> Tuple[datetime, datetime]:
	left, right = r.split( '..', maxsplit=1 )
	return parse_floor( left ), parse_ceil( right )

def parse_floor_str( s: str ) -> str:
	return parse_floor( s ).strftime( '%Y-%m-%d' )

def parse_floor( s: str ) -> datetime:
	if match( DATE_YEAR_PATTERN, s ):
		dt = getarrow( s ).floor( 'year' )
	elif match( DATE_YEAR_MONTH_PATTERN, s ):
		dt = getarrow( s ).floor( 'month' )
	elif match( DATE_YEAR_MONTH_DAY_PATTERN, s ):
		dt = getarrow( s ).floor( 'day' )
	else:
		dt = getarrow( 1, 1, 1 )
	return dt.datetime.astimezone( UTC )

def parse_ceil_str( s: str ) -> str:
	return parse_ceil( s ).strftime( '%Y-%m-%d' )

def parse_ceil( s: str ) -> datetime:
	if match( DATE_YEAR_PATTERN, s ):
		dt = getarrow( s ).ceil( 'year' )
	elif match( DATE_YEAR_MONTH_PATTERN, s ):
		dt = getarrow( s ).ceil( 'month' )
	elif match( DATE_YEAR_MONTH_DAY_PATTERN, s ):
		dt = getarrow( s ).ceil( 'day' )
	else:
		dt = getarrow( 9999, 12, 31 )
	return dt.datetime.astimezone( UTC )

def ceil( a: Arrow, frame: str ) -> str:
	return f'd"{a.ceil( frame ).isoformat()}"'

def floor( a: Arrow, frame: str ) -> str:
	return f'd"{a.floor( frame ).isoformat()}"'

