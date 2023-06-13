
from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from logging import getLogger
from re import compile as rx_compile, match
from sys import maxsize
from typing import Any, Dict, List, Literal, Tuple, Type

from arrow import Arrow, get as getarrow
from dateutil.tz import UTC
from rule_engine import Context, resolve_attribute, Rule, RuleSyntaxError, SymbolResolutionError

from tracs.registry import Registry

log = getLogger( __name__ )

TIME_FRAMES = Literal[ 'year', 'quarter', 'month', 'week', 'day' ]

TRUE_FALSE = rx_compile( r'^(true|false)$' )

INT_PATTERN = '^(?P<value>\d+)$'
INT_LIST = rx_compile( '^\d+(,\d+)*$' )
INT_RANGE_PATTERN = rx_compile( '^(?P<range_from>\d+)?\.\.(?P<range_to>\d+)?$' )

NUMBER_PATTERN = '^(?P<value>\d+(\.\d+)?)$'

QUOTED_STRING_PATTERN = '^"(?P<value>.*)"$'

KEYWORD_PATTERN = '^[a-zA-Z][\w-]*$'

LIST_PATTERN = '^(\w+)(,(\w+))+$'
RANGE_PATTERN = '^(?P<range_from>\d[\d\.\:-]+)?(\.\.)(?P<range_to>\d[\d\.\:-]+)?$'

DATE_PATTERN = '^(?P<year>[12]\d\d\d)-(?P<month>[01]\d)-(?P<day>[0-3]\d)$'
DATE_YEAR_PATTERN = '^(?P<year>[12]\d\d\d)$'
DATE_YEAR_MONTH_PATTERN = '^(?P<year>[12]\d\d\d)-(?P<month>[01]\d)$'
DATE_YEAR_MONTH_DAY_PATTERN = DATE_PATTERN
FUZZY_DATE_PATTERN = '^(?P<year>[12]\d\d\d)(-(?P<month>[01]\d))?(-(?P<day>[0-3]\d))?$'

TIME_PATTERN = '^(?P<hour>[0-1]\d|2[0-4]):(?P<minute>[0-5]\d):(?P<second>[0-5]\d)$'
FUZZY_TIME_PATTERN = '^(?P<hour>[0-1]\d|2[0-4])(:(?P<minute>[0-5]\d)(:(?P<second>[0-5]\d))?)?$'

SHORT_RULE_PATTERN = r'^(\w+)(:|=)([\w\"\.].+)$' # short version: id=10 or id:10 for convenience, value must begin with alphanum or "
RULE_PATTERN = '^(\w+)(==|!=|=~|!~|>=|<=|>|<|=|:)([\w\"\.].+)*$'

# type hints to be able to parse certain string correctly (i.e. 2022 as date, not as int)
RESOLVER_TYPES: Dict[str, Type] = {
	'date': datetime,
	'time': time,
}

def resolve_custom_attribute( thing: Any, name: str ) -> Any:
	try:
		return resolve_attribute( thing, name )
	except SymbolResolutionError:
		try:
			return getattr( thing.vf, name )
		except AttributeError:
			raise SymbolResolutionError( thing=thing, symbol_name=name )

# this should also work ...
def resolve_custom_attribute_2( thing: Any, name: str ) -> Any:
	try:
		return thing.getattr( name, quiet=False )
	except AttributeError:
		raise SymbolResolutionError( thing=thing, symbol_name=name )

# CONTEXT = Context( default_value=None, resolver=resolve_custom_attribute )
CONTEXT = Context( resolver=resolve_custom_attribute )

# rules parser

def parse_rules( *rules: str ) -> List[Rule]:
	return [parse_rule( r ) for r in rules]

def parse_rule( rule: str ) -> Rule:

	rule: str = normalize( rule ) # normalize rule, used for preprocessing special cases
	rule: str = preprocess( rule ) # preprocess, not used at the moment
	rule: Rule = process( rule )
	rule: Rule = postprocess( rule ) # create and postprocess parsed rule

	return rule

def normalize( rule: str ) -> str:

	left, op, right, normalized_rule = None, None, None, None

	if match( INT_PATTERN, rule ): # integer number only
		left, right, normalized_rule = 'id', rule, f'id == {rule}'

	elif m := INT_RANGE_PATTERN.fullmatch( rule ):
		left, right = 'id', rule
		range_from, range_to = m.groups()
		if range_from and not range_to:
			normalized_rule = f'id >= {range_from}'
		elif not range_from and range_to:
			normalized_rule = f'id <= {range_to}'
		else:
			normalized_rule = f'id >= {range_from} and id <= {range_to}'

	elif INT_LIST.fullmatch( rule ):
		left, right, normalized_rule = 'id', rule, f'id in [{rule}]'

	elif match( KEYWORD_PATTERN, rule ):  # keywords
		if rule in Registry.rule_keywords.keys():
			right, normalized_rule = rule, Registry.rule_keywords[rule]( rule )
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
			elif TRUE_FALSE.match( right ):
				normalized_rule = f'{left} == {right}'
			else:
				normalized_rule = f'{left} == "{right}"'

		elif op == ':':
			if right is None:
				normalized_rule = f'{left} == null'

			elif match( NUMBER_PATTERN, right ):
				if RESOLVER_TYPES.get( left ) is datetime: # years are caught by this regex already ...
					normalized_rule = f'{left} >= d"{parse_floor_str( right )}" and {left} <= d"{parse_ceil_str( right )}"'
				else:
					normalized_rule = f'{left} == {right}'

			elif TRUE_FALSE.match( right ):
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

	# apply normalizer, if a normalizer for the left side of the expression exists
	if left in Registry.rule_normalizers:
		normalized_rule = Registry.rule_normalizers[left]( left, op, right, normalized_rule )  # pass the already normalized rule, just in case a normalizer is interested

	# log rule
	log.debug( f'normalized rule {rule} to {normalized_rule}' )

	# error if no rule was created
	if not normalized_rule:
		raise RuleSyntaxError( f'syntax error in expression "{rule}"' )

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
	"""
	Creates a rule from a normalized and preprocessed rule string.

	:param rule: rule string to use for rule creation
	:return: newly created rule
	"""
	return Rule( rule, CONTEXT )

def postprocess( rule: Rule ) -> Rule:
	"""
	Reserved for future use, does nothing at the moment.

	:param rule: rule to postprocess
	:return: postprocessed rule
	"""
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

def ceil( a: Arrow, frame: TIME_FRAMES ) -> str:
	return f'd"{a.ceil( frame ).isoformat()}"'

def floor( a: Arrow, frame: TIME_FRAMES ) -> str:
	return f'd"{a.floor( frame ).isoformat()}"'
