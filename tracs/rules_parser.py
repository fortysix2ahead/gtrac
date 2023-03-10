
from __future__ import annotations

from datetime import datetime
from logging import getLogger
from re import match
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Type

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

KEYWORD_PATTERN = '^[a-zA-Z][\w-]*$'

SHORT_RULE_PATTERN = r'^(\w+)(:|=)([\w\"].+)$' # short version: id=10 or id:10 for convenience, value must begin with alphanum or "
RULE_PATTERN = '^(\w+)(==|!=|=~|!~|>=|<=|>|<|=|:)([\w\"].+)$'

RULES: Dict[str, Type[Rule]] = {
	'id': NumberEqRule
}

KEYWORDS: Dict[str, Callable] = {
	'thisyear': lambda s: f'year == {datetime.utcnow().year}',
	# todo: this needs to be detected automatically
	'bikecitizens': lambda s: f'"bikecitizens" in classifiers',
	'local': lambda s: f'"local" in classifiers',
	'polar': lambda s: f'"polar" in classifiers',
	'strava': lambda s: f'"strava" in classifiers',
	'waze': lambda s: f'"waze" in classifiers',
}

NORMALIZERS: Dict[str, Callable] = {
	'classifier': lambda s: f'"{s}" in classifiers',
}

# custom field/attribute resolvers, needed to access "virtual fields" which do not exist
RESOLVERS: Dict[str, Callable] = {
	'classifiers': lambda a: list( map( lambda s: s.split( ':', 1 )[0], a.uids ) ),
	'year': lambda a: a.time.year
}

def resolve_custom_attribute( thing: Any, name: str ):
	return RESOLVERS[name]( thing ) if name in RESOLVERS.keys() else resolve_attribute( thing, name )

# CONTEXT = Context( default_value=None, resolver=resolve_custom_attribute )
CONTEXT = Context( resolver=resolve_custom_attribute )

# predefined rules

# rules parser

def parse_rules( *rules: str ) -> List[Rule]:
	return [parse_rule( r ) for r in rules]

def parse_rule( rule: str ) -> Rule:

	rule: str = normalize( rule ) # normalize rule, used for preprocessing special cases
	rule: str = preprocess( rule ) # preprocess, not used at the moment
	rule: DefaultRule = process( rule )
	rule: Rule = postprocess( rule ) # create and postprocess parsed rule

	return rule

def normalize( rule: str ) -> str:

	normalized_rule = rule

	if m := match( INT_PATTERN, rule ): # integer number only
		normalized_rule = f'id == {rule}'

	elif m := match( KEYWORD_PATTERN, rule ):  # keywords
		if rule in KEYWORDS:
			normalized_rule = KEYWORDS[rule]( rule )
		else:
			raise RuleSyntaxError( f'syntax error: unsupported keyword "{rule}"' )

	elif m := match( RULE_PATTERN, rule ): #
		left, op, right = m.groups()
		if op == '=':
			normalized_rule = f'{left} == {right}'
		elif op == ':':
			if left in NORMALIZERS:
				normalized_rule = NORMALIZERS[left]( right )
			else:
				normalized_rule = f'{left} == {right}'

	else:
		raise RuleSyntaxError( f'syntax error in expression "{rule}"' )

	if normalized_rule != rule:
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
