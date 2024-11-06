from typing import Any, List

from rich.pretty import Pretty

# formatting

def fmt_default( obj: Any, format: str, locale: str ) -> str|Pretty:
	return str( obj ) if obj is not None else ''

# styling

def style( *items: str, style: str ) -> List[str]:
	return [f'[{style}]{i}[/{style}]' for i in items]
