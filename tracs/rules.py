from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as datafield
from typing import Any
from typing import ClassVar
from typing import List

from rule_engine import Context
from rule_engine.ast import ComparisonExpression
from rule_engine.ast import ExpressionBase
from rule_engine.ast import FloatExpression
from rule_engine.ast import SymbolExpression

@dataclass
class Rule:
	field: str = datafield( default=None )
	operator: str = datafield( default=None )
	value: Any = datafield( default=None )

	context: Context = datafield( default=Context(), init=False )
	expr: ExpressionBase = datafield( default=None, init=False )

	compatible_fields: ClassVar[List[str]] = datafield( default=[] )
	compatible_ops: ClassVar[List[str]] = datafield( default=[] )

	def __post_init__( self ):
		self.expr = self.__post_init_expr__().reduce()

	def __post_init_expr__( self ) -> ExpressionBase:
		pass

	def evaluate( self, obj: Any ) -> bool:
		return self.expr.evaluate( obj )

@dataclass
class NumberEqRule( Rule ):

	compatible_fields: ClassVar[List[str]] = datafield( default=['id'] )
	compatible_ops: ClassVar[List[str]] = datafield( default=['==', '!='] )

	def __post_init_expr__( self ):
		self.left = SymbolExpression( self.context, self.field )
		if self.operator == '==':
			self.operator = 'eq'
		self.value = int( self.value )
		self.right = FloatExpression( self.context, self.value )
		return ComparisonExpression( self.context, 'eq', self.left, self.right )
