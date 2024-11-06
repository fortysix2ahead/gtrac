from datetime import datetime
from typing import Any, List, Optional

from babel.dates import format_datetime
from rich.pretty import Pretty

DEFAULT_LOCALE = 'en'

DEFAULT_FORMAT = 'medium'

# formatting

def fmt_default( obj: Any, fmt: Optional[str] = None, locale: Optional[str] = None ) -> str|Pretty:
	return str( obj ) if obj is not None else ''

def fmt_datetime( obj: datetime, fmt: Optional[str] = None, locale: Optional[str] = None ) -> str|Pretty:
	return format_datetime( obj, fmt or DEFAULT_FORMAT, None, locale or DEFAULT_LOCALE )

# styling

def style( *items: str, style: str ) -> List[str]:
	return [f'[{style}]{i}[/{style}]' for i in items]
