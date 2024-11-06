
from logging import getLogger
from pathlib import Path
from re import split
from typing import List

from dynaconf.vendor.box.exceptions import BoxKeyError
from rich import box
from rich.pretty import Pretty as pp
from rich.table import Table

from tracs.activity import Activity
from tracs.config import ApplicationContext, console
from tracs.core import VirtualField
from tracs.ui.tables import create_table
from tracs.utils import fmt, red

log = getLogger( __name__ )

# noinspection PyTestUnpassedFixture
def list_activities( activities: List[Activity], sort: str = None, reverse: bool = False, format_name: str = False, fields: str = None, ctx: ApplicationContext = None ) -> None:
	sort = sort or 'starttime'
	fields = fields or []

	try:
		activities = sorted( activities, key=lambda act: ( ( att := getattr( act, sort, None ) ) is None, att ) )
	except (AttributeError, TypeError):
		log.warning( f'unable to sort for field "{sort}", falling back to "starttime"' )
		activities = sorted( activities, key=lambda act: getattr( act, "starttime" ) )

	if reverse:
		activities.reverse()

	if fields:
		list_fields = fields.split()
	elif format_name:
		try:
			list_fields = ctx.config.formats.list[format_name].split()
		except BoxKeyError:
			list_fields = ctx.config.formats.list['default'].split()
	else:
		list_fields = ctx.config.formats.list['default'].split()

	table = create_table(
		box_name=ctx.config.formats.table.box,
		headers=[ f for f in list_fields ],
		rows=[ a.format_as_list( *list_fields, suppress_errors=True ) for a in activities ],
	)

	if len( table.rows ) > 0:
		console.print( table )

def show_fields():
	table = Table( box=box.MINIMAL, show_header=True, show_footer=False )
	table.caption, table.caption_justify = 'Virtual fields are marked with \u24e5  and shown in yellow.', 'left'
	table.add_column( '', justify='center' )
	table.add_column( 'field' )
	table.add_column( 'type' )

	for f in sorted( Activity.fields( include_internal=False, include_virtual=True ), key=lambda fld: fld.name ):
		# name = f'{f.name} \u24e5' if isinstance( f, VirtualField ) else f.name
		virtual = '[yellow]\u24e5[/yellow]' if isinstance( f, VirtualField ) else ''
		name = f'[yellow]{f.name}[/yellow]' if isinstance( f, VirtualField ) else f.name
		table.add_row( virtual, name, pp( f.type ) )

	console.print( table )

def show_config( ctx: ApplicationContext ):
	table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
	table.add_column( justify='left', no_wrap=True )
	table.add_column( justify='left', no_wrap=True )

	table.add_row( 'configuration dir', ctx.config_dir )
	table.add_row( 'configuration file', pp( ctx.config_file ) )
	table.add_row( 'state file', pp( ctx.state_file ) )

	table.add_section()

	table.add_row( 'library', pp( ctx.lib_dir ) )
	table.add_row( 'database dir', pp( ctx.db_dir ) )

	table.add_section()

	for s in ctx.registry.services.values():
		table.add_row( f'{s.name} activities:', pp( Path( ctx.db_dir, s.name ) ) )

	table.add_section()

	#table.add_row( 'plugins dir', pp( ctx.plugins_dir ) )
	#table.add_row( 'overlay dir', pp( ctx.overlay_dir ) )

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
