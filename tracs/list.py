
from dataclasses import fields
from pathlib import Path
from re import split
from typing import List

from confuse.exceptions import NotFoundError
from logging import getLogger
from rich import box
from rich.pretty import Pretty as pp
from rich.table import Table

from .activity import Activity
from .config import ApplicationContext
from .config import console
from .registry import Registry
from .utils import fmt
from .utils import red

log = getLogger( __name__ )

def list_activities( activities: List[Activity], sort: str = False, reverse: bool = False, format_name: str = False, ctx: ApplicationContext = None ) -> None:
	sort = sort or 'time'

	if sort in Activity.fieldnames():
		activities.sort( key=lambda act: getattr( act, sort, None ) )
	else:
		log.warning( f'ignoring unknown sort field "{sort}", falling back to "time"' )

	if reverse:
		activities.reverse()

	try:
		list_format = ctx.config['formats']['list'][format_name].get()
	except NotFoundError:
		list_format = ctx.config['formats']['list']['default'].get()
	list_fields = list_format.split()

	headers = [ f for f in list_fields ]
	table = Table( box=box.MINIMAL, show_header=True, show_footer=False )

	for h in headers:
		table.add_column( f'[blue]{h}' )

	for a in activities:
		row = [ fmt( getattr( a, f ) ) if hasattr( a, f ) else None for f in list_fields ]
		table.add_row( *row )
		# table.add_row( pp( a.doc_id ), a.name, fmt( a.type ), fmt( a.localtime ), pp( a.uids ) )

	if len( table.rows ) > 0:
		console.print( table )

def inspect_activities( activities: [Activity] ) -> None:
	for a in activities:
		table = Table( box=box.MINIMAL, show_header=False, show_footer=False )

		table.add_row( '[blue]field[/blue]', '[blue]type[/blue]', '[blue]value[/blue]', '[blue]protected[/blue]', '[blue]persist[/blue]' )

		for f in sorted( Activity.fields(), key=lambda field: field.name ):
			table.add_row( f.name, f.type, pp( getattr( a, f.name ) ), pp( f.metadata.get( PROTECTED, False ) ), pp( f.metadata.get( PERSIST, True ) ) )

		console.print( table )

def inspect_resources() -> None:
	raise NotImplementedError

def inspect_registry() -> None:
	table = Table( box=box.MINIMAL, show_header=False, show_footer=False )

	table.add_row( '[bold bright_blue]Services[/bold bright_blue]' )
	table.add_row( '[blue]name[/blue]', '[blue]display name[/blue]', '[blue]class[/blue]', '[blue]enabled[/blue]' )
	for key, value in Registry.services.items():
		table.add_row( value.name, value.display_name, pp( value.__class__ ), pp( value.enabled ) )

	table.add_row( '[bold bright_blue]Document Classes[/bold bright_blue]' )
	table.add_row( '[blue]type[/blue]', '[blue][/blue]', '[blue]class[/blue]' )

	for key, value in Registry.document_classes.items():
		table.add_row( key, '', pp( f'{value.__module__}.{value.__name__}' ) )

	table.add_row( '[bold bright_blue]Importers[/bold bright_blue]' )
	table.add_row( '[blue]type[/blue]', '[blue][/blue]', '[blue]class[/blue]' )

	for key, value in Registry.importers.items():
		for v in value:
			table.add_row( key, '', pp( v.__class__ ) )

	console.print( table )

def show_fields():
	table = Table( box=box.MINIMAL, show_header=True, show_footer=False )
	table.add_column( 'field' )
	table.add_column( 'type' )
	table.add_column( 'aliases' )
	table.add_column( 'usable for filtering' )

	for f in fields( Activity ):
		table.add_row( f.name, f.type, pp( f.metadata.get( FILTER_ALIAS, None ) ), pp( f.metadata.get( FILTERABLE, False ) ) )

	console.print( table )

def show_config( ctx: ApplicationContext ):
	table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
	table.add_column( justify='left', no_wrap=True )
	table.add_column( justify='left', no_wrap=True )

	table.add_row( 'configuration dir', pp( ctx.cfg_dir ) )
	table.add_row( 'configuration file', pp( ctx.cfg_file ) )
	table.add_row( 'state file', pp( ctx.state_file ) )

	table.add_section()

	table.add_row( 'library', pp( ctx.lib_dir ) )
	table.add_row( 'database dir', pp( ctx.db_dir ) )

	table.add_section()

	for s in Registry.services.values():
		table.add_row( f'{s.display_name} activities:', pp( Path( ctx.db_dir, s.name ) ) )

	table.add_section()

	table.add_row( 'plugins dir', pp( ctx.plugins_dir ) )
	table.add_row( 'overlay dir', pp( ctx.overlay_dir ) )

	console.print( 'Locations', style='bold' )
	console.print( table )

	console.print( 'Configuration', style='bold' )
	console.print( ctx.config.dump() )

	console.print( 'State', style='bold' )
	console.print( ctx.state.dump() )

def shorten( s: str ) -> str:
	max_length = 120
	if len( str( s ) ) > max_length:
		start = int( max_length / 2 )
		end = int( len( str( s ) ) - (max_length / 2) )
		return f"{str( s )[:start]}{red('... ...')}{str( s )[end:]}"
	else:
		return s

def _type( o ) -> str:
	s = split( '^<.+\'(.+)\'>$', str( type( o ) ) )
	return s[1] if len( s ) > 2 else str( type( o ) )
