from datetime import datetime, timedelta
from typing import Any, List, Literal, Optional

from babel.dates import format_datetime, format_timedelta
from rich.pretty import Pretty

DEFAULT_LOCALE = 'en'

DATETIME_FORMATS = Literal[ 'full', 'long', 'medium', 'short' ]
TIMEDELTA_FORMATS = Literal[ 'narrow', 'short', 'medium', 'long' ]

DEFAULT_DATETIME_FORMAT = 'medium'
DEFAULT_TIMEDELTA_FORMAT = 'long'

# formatting

def fmt_default( obj: Any, fmt: Optional[str] = None, locale: Optional[str] = None ) -> str|Pretty:
	return str( obj ) if obj is not None else ''

def fmt_datetime( obj: datetime, fmt: DATETIME_FORMATS = None, locale: Optional[str] = None ) -> str|Pretty:
	fmt = fmt if fmt else DEFAULT_DATETIME_FORMAT
	return format_datetime( obj, fmt, None, locale or DEFAULT_LOCALE )

def fmt_timedelta( obj: timedelta, fmt: TIMEDELTA_FORMATS = None, locale: str = DEFAULT_LOCALE ) -> str|Pretty:
	try:
		fmt = fmt if fmt else DEFAULT_TIMEDELTA_FORMAT
		return format_timedelta( obj, format=fmt, locale=locale or DEFAULT_LOCALE )
	except TypeError:
		return ''

# styling

def style( *items: str, style: str ) -> List[str]:
	return [f'[{style}]{i}[/{style}]' for i in items]
