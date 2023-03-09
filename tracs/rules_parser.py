
from __future__ import annotations

from logging import getLogger
from re import match
from typing import Dict
from typing import List
from typing import Type

from tracs.rules import Rule
from tracs.rules import NumberEqRule

log = getLogger( __name__ )

INT_PATTERN = '^(?P<value>\d+)$'
INT_LIST_PATTERN = '^(?P<values>(\d+,)+(\d+))$'
INT_RANGE_PATTERN = '^(?P<range_from>\d+)?\.\.(?P<range_to>\d+)?$'

KEYWORD_PATTERN = '^[a-zA-Z][\w-]*$'

#SHORT_RULE_PATTERN = '^(\w+)(:|=)(.+)$' # short version: id=10 or id:10 for convenience
SHORT_RULE_PATTERN = r'^(\w+)(:|=)([\w\"].+)$' # short version: id=10 or id:10 for convenience, value must begin with alphanum or "
RULE_PATTERN = '^(\w+)(==|!=|=~|!~|>=|<=|>|<)(.+)$'

RULES: Dict[str, Type[Rule]] = {
	'id': NumberEqRule
}

# predefined rules

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

	if m := match( INT_PATTERN, rule ): # integer number only
		normalized_rule = f'id=={rule}'
	elif m := match( SHORT_RULE_PATTERN, rule ):  # short rules
		normalized_rule = f'{m.groups()[0]}=={m.groups()[2]}'
	else:
		normalized_rule = rule

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
	if m := match( RULE_PATTERN, rule ):
		return process_expr( *m.groups() )
	else:
		raise RuntimeError( f'unable to parse rule {rule}' )

def process_expr( left: str, op: str, right: str ) -> Rule:
	if left not in RULES.keys():
		raise RuntimeError( f'unknown/unsupported query field {left}' )

	if op not in RULES.get( left ).compatible_ops:
		raise RuntimeError( f'unknown/unsupported operator "{op}" for query field {left}' )

	rule = create_rule( left, op, right )
	return rule

def create_rule( left: str, op: str, right: str ) -> Rule:
	return RULES.get( left )( field=left, operator=op, value=right )

def postprocess( rule: Rule ) -> Rule:
	return  rule
