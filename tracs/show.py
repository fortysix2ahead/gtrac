
from pathlib import Path

from confuse.exceptions import NotFoundError
from rich import box
from rich.pretty import Pretty as pp
from rich.table import Table

from .activity import Activity
from .activity import Resource
from .config import ApplicationContext
from .config import console
from .plugins import Registry
from .service import Service
from .utils import fmt

def show_activity( activities: [Activity], ctx: ApplicationContext, display_raw: bool = False, verbose: bool = True, format_name: str = None ) -> None:

	if format_name == 'all':
		show_fields = [ f.name for f in Activity.fields() ]
		show_fields.sort()
	else:
		try:
			show_format = ctx.config['formats']['show'][format_name].get()
		except NotFoundError:
			show_format = ctx.config['formats']['show']['default'].get()
		show_fields = show_format.split()

	for a in activities:
		if display_raw:
			table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
			table.add_row( '[blue]field[/blue]', '[blue]value[/blue]' )

			for f in sorted( Activity.fields(), key=lambda field: field.name ):
				table.add_row( f.name, pp( getattr( a, f.name ) ) )

			console.print( table )

			table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
			table.add_row( '[bold bright_blue]Resources[/bold bright_blue]' )
			table.add_row( '[blue]id[/blue]', '[blue]name[/blue]', '[blue]path[/blue]', '[blue]exists[/blue]', '[blue]type[/blue]', '[blue]uid[/blue]', '[blue]status[/blue]', '[blue]source[/blue]' )
			for uid in a.uids:
				resources = ctx.db.find_resources( uid )
				for r in resources:
					resource_path = Registry.services.get( r.classifier ).path_for( resource=r )
					path_exists = '[bright_green]\u2713[/bright_green]' if resource_path.exists() else '[bright_red]\u2716[/bright_red]'
					table.add_row( pp( r.doc_id ), r.name, r.path, path_exists, r.type, r.uid, pp( r.status ), r.source )

			console.print( table )

		else:
			table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
			rows = [ [ field, getattr( a, field ) ] for field in show_fields ]

			for row in rows:
				if row[1] is not None and row[1] != '' and row[1] != [] and row[1] != {}:
					table.add_row( row[0], fmt( row[1] ) )

			console.print( table )
			console.print( '\u00b9 Proper timezone support is currently missing, local timezone is displayed' )

			if verbose:
				table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
				table.add_row( '[bold bright_blue]URLs and Locations:[/bold bright_blue]' )
				for uid in a.uids:
					classifier, local_id = uid.split( ':', 1 )
					table.add_row( classifier, Service.url_for_uid( uid ) )
				for uid in a.uids:
					path = Path( ctx.db_dir, Service.path_for_uid( uid ) )
					table.add_row( 'local db', f'{str( path )}/' )

				console.print( table )

				table = Table( box=box.MINIMAL, show_header=False, show_footer=False )
				table.add_row( '[bold bright_blue]Resources:[/bold bright_blue]' )
				table.add_row( '[blue]id[/blue]', '[blue]path[/blue]', '[blue]type[/blue]', '[blue]URL[/blue]' )
				for uid in a.uids:
					resources = ctx.db.find_resources( uid ) if ctx else []
					for r in resources:
						resource_path = Registry.services.get( r.classifier ).path_for( resource=r )
						path_exists = '[bright_green]\u2713[/bright_green]' if resource_path.exists() else '[bright_red]\u2716[/bright_red]'
						resource_url = Registry.services.get( r.classifier ).url_for( resource=r )
						table.add_row( pp( r.doc_id ), f'{r.path} {path_exists}', r.type, resource_url )

				console.print( table )
