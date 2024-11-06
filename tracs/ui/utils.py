from datetime import datetime, timedelta
from typing import Any, List, Literal

from babel.dates import format_datetime, format_timedelta
from babel.numbers import format_decimal
from rich.pretty import Pretty

DEFAULT_LOCALE = 'en'

DATETIME_FORMATS = Literal[ 'full', 'long', 'medium', 'short' ]
TIMEDELTA_FORMATS = Literal[ 'narrow', 'short', 'medium', 'long' ]

DEFAULT_DATETIME_FORMAT = 'medium'
DEFAULT_TIMEDELTA_FORMAT = 'long'

# formatting

def fmt_default( obj: Any, fmt: str = None, locale: str = None ) -> str|Pretty:
	return str( obj ) if obj is not None else ''

def fmt_decimal( obj: float, fmt: str = None, locale: str = None ) -> str|Pretty:
	fmt = fmt or '#,###.#'
	locale = locale or DEFAULT_LOCALE
	return '' if obj is None else format_decimal( obj, format=fmt, locale=locale )

def fmt_datetime( obj: datetime, fmt: DATETIME_FORMATS = None, locale: str = None ) -> str|Pretty:
	fmt = fmt or DEFAULT_DATETIME_FORMAT
	locale = locale or DEFAULT_LOCALE
	return format_datetime( obj, fmt, None, locale )

def fmt_timedelta( obj: timedelta, fmt: TIMEDELTA_FORMATS = None, locale: str = None ) -> str|Pretty:
	try:
		fmt = fmt or DEFAULT_TIMEDELTA_FORMAT
		locale = locale or DEFAULT_LOCALE
		return format_timedelta( obj, format=fmt, locale=locale )
	except TypeError:
		return ''

# styling

def style( *items: str, style: str ) -> List[str]:
	return [f'[{style}]{i}[/{style}]' for i in items]
