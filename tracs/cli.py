
from itertools import chain
from logging import getLogger
from typing import List, Optional, Tuple

from click import argument, Choice, Context as ClickContext, group, option, pass_context, pass_obj, Path as ClickPath
from click_shell import make_click_shell
from rule_engine import RuleSyntaxError

from tracs.activity import Activity
from tracs.aio import export_activities, import_activities, open_activities, reimport_activities
from tracs.application import Application
from tracs.config import ApplicationContext, APPNAME
from tracs.db import maintain_db, status_db
from tracs.edit import edit_activities, equip_activities, modify_activities, rename_activities, set_activity_type, tag_activities, unequip_activities, \
	untag_activities
from tracs.fsio import backup_db, restore_db
from tracs.group import group_activities, part_activities, ungroup_activities, unpart_activities
from tracs.inspct import inspect_activities, inspect_keywords, inspect_plugins, inspect_registry, inspect_resources
from tracs.link import link_activities
from tracs.list import list_activities, show_config, show_fields
from tracs.setup import setup as setup_application
from tracs.show import show_activities, show_aggregate, show_equipments, show_keywords, show_resources, show_tags, show_types
from tracs.validate import validate_activities

log = getLogger( __name__ )

# global application instance: we probably don't need this, but it's accessible from here
APPLICATION_INSTANCE: Optional[Application] = None

def setup_context( *args, **kwargs ) -> None:
	pass

def teardown_context( *args, **kwargs ) -> None:
	pass

@group()
# @shell( prompt=f'{APPNAME} > ', intro=f'Starting interactive shell mode, enter <exit> to leave this mode again, use <{APPNAME} --help> for help ...' )
@option( '-c', '--configuration', is_flag=False, required=False, help='configuration area location', metavar='PATH' )
@option( '-l', '--library', is_flag=False, required=False, help='library location', metavar='PATH' )
@option( '-v', '--verbose', is_flag=True, default=None, required=False, help='be more verbose when logging' )
@option( '-d', '--debug', is_flag=True, default=None, required=False, help='enable output of debug messages' )
@option( '-f', '--force', is_flag=True, default=None, required=False, help='forces operations to be carried out' )
@option( '-j', '--json', is_flag=True, default=None, required=False, help='forces operations to be carried out' )
@option( '--feature', required=False, multiple=True, help='forces operations to be carried out', type=str )
@option( '-p', '--pretend', is_flag=True, default=None, required=False, help='pretends to work, only simulates everything and does not persist any changes' )
@pass_context
def cli( ctx: ClickContext, configuration, library, force, verbose, pretend, debug, json, feature: Tuple[str] ):

	ctx.call_on_close( teardown_context )

	global APPLICATION_INSTANCE
	APPLICATION_INSTANCE = Application.instance(
		configuration=configuration,
		library=library,
		verbose=verbose,
		debug=debug,
		force=force,
		pretend=pretend,
		json=json,
		features=list( feature )
	)

	ctx.obj = APPLICATION_INSTANCE.ctx # save newly created context object

	# migrate_application( ctx.obj, None ) # check if migration is necessary

@cli.command( hidden=True )
@option( '-b', '--backup', is_flag=True, required=False, help='creates a backup of the internal database' )
@option( '-m', '--maintenance', is_flag=False, flag_value='__show_maintenance_functions__', required=False, type=str, help='executes database maintenance', metavar='FUNCTION' )
@option( '-r', '--restore', is_flag=True, required=False, help='restores the last version of the database from the backup' )
@option( '-s', '--status', is_flag=True, required=False, help='prints some db status information' )
@pass_obj
def db( ctx: ApplicationContext, backup: bool, maintenance: str, restore: bool, status: bool ):
	if backup:
		backup_db( ctx.db_fs, ctx.backup_fs )
	elif maintenance:
		maintain_db( ctx, maintenance=maintenance if maintenance != '__show_maintenance_functions__' else None )
	elif restore:
		restore_db( ctx.db_fs, ctx.backup_fs, ctx.force )
	elif status:
		status_db( ctx )

@cli.command( help='prints the current configuration' )
@pass_obj
def config( ctx: ApplicationContext ):
	show_config( ctx )

@cli.command( hidden=True, help='commits changes to the database, intended to be used in shell mode' )
@pass_obj
def commit( ctx: ApplicationContext ):
	ctx.db.commit()

@cli.command( help='prints information about fields that can be used for filtering' )
def fields():
	show_fields()

@cli.command( 'import', hidden=True, help='imports activities' )
@option( '-a', '--fetch-all', required=False, hidden=True, default=False, is_flag=True, type=bool, help='always fetch all activities instead of the most recent ones' )
@option( '-c', '--classifier', required=False, type=str, help='classifier to use during import' )
@option( '-m', '--move', required=False, hidden=True, is_flag=True, help='remove resources after import (dangerous, applies for imports from takeouts only)' )
@option( '-sd', '--skip-download', hidden=True, required=False, is_flag=True, help='skips download of activities' )
@option( '-t', '--from-takeouts', required=False, is_flag=True, help='imports activities from takeouts folder (plugin needs to support this)' )
@argument( 'sources', nargs=-1 )
@pass_obj
def imprt( ctx: ApplicationContext,
           sources,
           fetch_all: bool,
           skip_download: bool = False,
           move: bool = False,
           from_takeouts: str = None,
           classifier: str = None,
           ):
	activities = import_activities( ctx, sources, fetch_all=fetch_all, skip_download=skip_download, move=move, from_takeouts=from_takeouts, classifier=classifier )

	if ctx.json:
		ctx.console.print_json( data=activities.to_dict() )

@cli.command( help='fetches activity summaries', hidden=True )
@argument( 'sources', nargs=-1 )
@pass_obj
def fetch( ctx, sources: List[str] ):
	import_activities( ctx, importer=None, sources=sources, skip_download=True, skip_link=True )

@cli.command( help='downloads activities', hidden=True )
@argument( 'filters', nargs=-1 )
@pass_obj
def download( ctx: ApplicationContext, filters ):
	activities = _flt( *filters )
	activity_uids = list( set( chain( *[a.uids for a in activities] ) ) )
	if activity_uids:
		import_activities( ctx, None, sources = activity_uids, skip_fetch = True )

@cli.command( help='creates a tree of links resources of activities', hidden=True )
@argument( 'filters', nargs=-1 )
@pass_obj
def link( ctx: ApplicationContext, filters ):
	link_activities( ctx, _flt( *filters ) )

@cli.command( 'list', help='lists activities' )
@option( '-s', '--sort', is_flag=False, required=False, help='sorts the output according to an attribute' )
@option( '-r', '--reverse', is_flag=True, required=False, help='reverses sort order' )
@option( '-f', '--format', 'format_name', is_flag=False, required=False, type=str, help='uses the format with the provided name when printing', metavar='FORMAT' )
@option( '-l', '--fields', is_flag=False, required=False, type=str, help='specify the fields to be printed, cannot be used together with -f', metavar='FORMAT' )
@argument('filters', nargs=-1)
@pass_obj
def ls( ctx: ApplicationContext, sort, reverse, format_name, fields, filters ):
	list_activities( _flt( *filters ), sort=sort, reverse=reverse, format_name=format_name, fields=fields, ctx=ctx )

@cli.command( help='shows details about activities and resources' )
@option( '-f', '--format', 'format_name', is_flag=False, required=False, type=str, hidden=True, help='uses the format with the provided name when printing', metavar='FORMAT' )
@option( '-w', '--raw', is_flag=True, required=False, hidden=True, help='display raw data' )
@option( '-r', '--resource', is_flag=True, required=False, hidden=True, default=False, help='display information on resources' )
@option( '-v', '--verbose', is_flag=True, required=False, default=False, help='verbose, shows more information' )
@argument('filters', nargs=-1)
@pass_obj
def show( ctx: ApplicationContext, filters, raw, format_name, resource, verbose ):
	if resource:
		show_resources( _flt( *filters ), ctx=ctx, display_raw=raw, verbose=verbose, format_name=format_name )
	else:
		show_activities( _flt( *filters ), ctx=ctx, display_raw=raw, verbose=verbose, format_name=format_name )

@cli.command( help='groups activities' )
@argument( 'filters', nargs=-1 )
@pass_obj
def group( ctx: ApplicationContext, filters: List[str] ):
	group_activities( ctx, _flt( *filters ), force=ctx.force )

@cli.command( help='reverts activity groupings' )
@option( '-k', '--keep', is_flag=True, required=False, hidden=True, default=False, help='do not remove group after ungrouping' )
@argument( 'filters', nargs=-1 )
@pass_obj
def ungroup( ctx: ApplicationContext, filters: List[str], keep: bool = False ):
	ungroup_activities( ctx, _flt( *filters ), keep, force=ctx.force, pretend=ctx.pretend )

@cli.command( hidden=True, help='combines activities to multipart activities' )
@argument( 'filters', nargs=-1 )
@pass_obj
def part( ctx: ApplicationContext, filters: List[str] ):
	part_activities( _flt( *filters ), force=ctx.force, pretend=ctx.pretend, ctx=ctx )

@cli.command( hidden=True, help='removes multipart activities' )
@argument( 'filters', nargs=-1 )
@pass_obj
def unpart( ctx: ApplicationContext, filters: List[str] ):
	unpart_activities( _flt( *filters ), force=ctx.force, pretend=ctx.pretend, ctx=ctx )

@cli.command( help='modifies activities' )
@option( '-f', '--field', is_flag=False, required=True, help='field to modify' )
@option( '-v', '--value', is_flag=False, required=True, help='new field value' )
@argument( 'filters', nargs=-1 )
@pass_context
def modify( ctx, filters, field, value ):
	modify_activities( activities=ctx.obj.db.find( filters ), field=field, value=value, ctx = ctx.obj, force=ctx.obj.force, pretend=ctx.obj.pretend )

@cli.command( hidden=True, help='edits activities' )
@argument( 'filters', nargs=-1 )
def edit( identifier ):
	edit_activities( [Application.instance().db.find_by_id( identifier )] )

@cli.command( help='renames activities' )
@argument( 'filters', nargs=-1 )
@pass_obj
def rename( ctx: ApplicationContext, filters: str ):
	rename_activities( _flt( *filters ), ctx, ctx.force, ctx.pretend )
	ctx.db.commit()

@cli.command( help='reimports activities' )
@option( '-fr', '--from-remote', is_flag=False, required=False, help='reimport from remote source instead of local data only' )
@option( '-if', '--ignore-field', is_flag=False, required=False, multiple=True, help='fields to be ignored when calculating new field values' )
@option( '-o', '--offset', is_flag=False, required=False, help='offset for correcting value for time' )
@option( '-r', '--include-recordings', is_flag=True, required=False, help='include data from recordings like GPX or TCX when reimporting' )
# @option( '-s', '--strategy', is_flag=False, required=False, hidden=True, help='strategy to use when calculating fields (experimental)' )
@option( '-tz', '--timezone', is_flag=False, required=False, help='timezone for calculating value for local time' )
@argument( 'filters', nargs=-1 )
@pass_obj
def reimport( ctx: ApplicationContext, filters, include_recordings: bool = False, from_remote: bool = False, strategy: str = None, offset: str = None, timezone: str = None, ignore_field: Tuple = None ):
	reimport_activities(
		activities=_flt( *filters ),
		include_recordings=include_recordings,
		from_remote=from_remote,
		ignore_fields=list( ignore_field ),
		strategy=strategy,
		offset=offset,
		timezone=timezone,
		ctx=ctx
	)

@cli.command( 'open', help='opens activities in an external application' )
@argument( 'filters', nargs=-1 )
@pass_obj
def open_cmd( ctx: ApplicationContext, filters ):
	open_activities( ctx, _flt( *filters ) )

@cli.command( help='export activities/resources' )
@option( '-a', '--aggregate', required=False, is_flag=True )
@option( '-f', '--format', 'fmt', required=False, type=Choice( ['csv', 'geojson', 'gpx'], case_sensitive=False ), metavar='FORMAT' )
@option( '-l', '--overlay', required=False, is_flag=True, hidden=True )
@option( '-o', '--output', required=False, type=ClickPath(), metavar='PATH' )
@argument( 'filters', nargs=-1 )
@pass_obj
def export( ctx: ApplicationContext, fmt: str, output: str, aggregate: bool, overlay: bool, filters ):
	export_activities( ctx, _flt( *filters ), fmt=fmt, output=output, aggregate=aggregate, overlay=overlay )

@cli.command( 'set', hidden=True, help='sets field values manually' )
@argument( 'filters', nargs=-1 )
def set_cmd( filters ):
	pass

@cli.command( hidden=True, help='unsets field values' )
@argument( 'filters', nargs=-1 )
def unset( filters ):
	pass

@cli.command( help='Displays all existing keywords' )
@pass_obj
def keywords( ctx: ApplicationContext ):
	show_keywords( ctx )

@cli.command( help='Tags activities' )
@option( '-a', '--all', 'all_tags', is_flag=True, required=False, help='lists all existing tags' )
@option( '-t', '--tag', 'tags', is_flag=False, required=False, multiple=True, help='tag to add to an activity' )
@argument( 'filters', nargs=-1 )
@pass_obj
def tag( ctx: ApplicationContext, filters, tags, all_tags: bool = False ):
	if all_tags or not tags:
		show_tags( ctx )
	else:
		tags = list( set( chain( *[ t.split( ',' ) for t in tags ] ) ) )
		tag_activities( _flt( *filters ), tags=tags, ctx=ctx )
		ctx.db.commit()

@cli.command( help='Removes tags from activities' )
@option( '-t', '--tag', 'tags', is_flag=False, required=True, multiple=True, help='tag to remove from an activity' )
@argument( 'filters', nargs=-1 )
@pass_obj
def untag( ctx: ApplicationContext, filters, tags ):
	tags = list( set( chain( *[ t.split( ',' ) for t in tags ] ) ) )
	untag_activities( _flt( *filters ), tags=tags, ctx=ctx )
	ctx.db.commit()

@cli.command( help='Add equipment to an activity' )
@option( '-a', '--all', 'all_equipments', is_flag=True, required=False, help='lists all equipments' )
@option( '-e', '--equipment', 'equipments', is_flag=False, required=False, multiple=True, help='equipment to add to an activity' )
@argument( 'filters', nargs=-1 )
@pass_obj
def equip( ctx: ApplicationContext, filters, equipments, all_equipments: bool = False ):
	if all_equipments or not equipments:
		show_equipments( ctx )
	else:
		equipments = list( set( chain( *[ e.split( ',' ) for e in equipments ] ) ) )
		equip_activities( _flt( *filters ), equipments=equipments, ctx=ctx )
		ctx.db.commit()

@cli.command( help='Removes equipment from activities' )
@option( '-e', '--equipment', 'equipments', is_flag=False, required=True, multiple=True, help='equipment to remove from an activity' )
@argument( 'filters', nargs=-1 )
@pass_obj
def unequip( ctx: ApplicationContext, filters, equipments ):
	equipments = list( set( chain( *[ e.split( ',' ) for e in equipments ] ) ) )
	unequip_activities( _flt( *filters ), equipments=equipments, ctx=ctx )
	ctx.db.commit()

@cli.command( help='application setup' )
@argument( 'services', nargs=-1 )
@pass_obj
def setup( ctx: ApplicationContext, services: List[str] ):
	setup_application( ctx, services )

@cli.command( help='Shows aggregated data (experimental + work in progress)' )
@argument( 'filters', nargs=-1 )
@pass_obj
def aggregate( ctx: ApplicationContext, filters ):
	show_aggregate( _flt( *filters ), ctx=ctx )

@cli.command( hidden=True, help='inspects activities/resources/internal registry' )
@option( '-j', '--json', is_flag=True, required=False, default=False, help='outputs json instead of text' )
@option( '-k', '--keywords', is_flag=True, required=False, help='inspects keywords (filters are ignored)' )
@option( '-p', '--plugins', is_flag=True, required=False, help='inspects all discoverable plugins (filter will be ignored)' )
@option( '-rg', '--registry', is_flag=True, required=False, help='inspects the internal registry (filter will be ignored)' )
@option( '-rs', '--resource', is_flag=True, required=False, help='inspects resources of activities' )
@argument( 'filters', nargs=-1 )
@pass_obj
def inspect( ctx: ApplicationContext, filters, json: bool, keywords: bool, plugins: bool, registry: bool, resource: bool ):
	if keywords:
		inspect_keywords( ctx, json )
	elif plugins:
		inspect_plugins( ctx )
	elif registry:
		inspect_registry( ctx.registry )
	elif resource:
		inspect_resources()
	else:
		inspect_activities( _flt( *filters ) )

@cli.command( hidden=True, help='Performs some validation and sanity tasks.' )
@option( '-c', '--correct', is_flag=True, required=False, default=False, help='try to correct found problems' )
@option( '-f', '--function', is_flag=False, required=False, help='restricts validation to the provided function only' )
@argument( 'filters', nargs=-1 )
@pass_obj
def validate( ctx: ApplicationContext, filters, function, correct ):
	validate_activities( _flt( *filters ), ctx=ctx, function=function, correct=correct )

@cli.command( help='starts application in interactive mode' )
@pass_context
def shell( ctx ):
	prompt=f'{APPNAME} > '
	intro=f'Starting interactive shell mode, enter <exit> to leave this mode, use <{APPNAME} --help> for help ...'
	make_click_shell( ctx.parent, prompt=prompt, intro=intro ).cmdloop()

@cli.command( 'type', help='sets the activity type' )
@option( '-t', '--type', 'activity_type', required=False, help='type to be set' )
@argument( 'filters', nargs=-1 )
@pass_obj
def set_type( ctx: ApplicationContext, filters, activity_type ):
	set_activity_type( ctx, _flt( *filters ), activity_type=activity_type )

@cli.command( help='displays all available activity types' )
@option( '-u', '--used-only', required=False, is_flag=True, default=False, help='display used types only' )
@pass_obj
def types( ctx, used_only: bool = False ):
	show_types( ctx, used_only=used_only )

@cli.command( help='Displays the version number and exits.' )
@pass_obj
def version( ctx: ApplicationContext ):
	if ctx.json:
		ctx.console.print_json( data={ 'version': '0.1.0' } )
	else:
		ctx.console.print( '0.1.0' )

def main( args=None ):
	cli()  # trigger cli

if __name__ == '__main__':
	main()

# helper

def _flt( *rules: str ) -> List[Activity]:
	try:
		rules = APPLICATION_INSTANCE.parser.parse_rules( *rules )
		activities = APPLICATION_INSTANCE.db.activities
		for r in rules:
			activities = r.filter( activities )
		return list( activities )

	except RuleSyntaxError as rse:
		APPLICATION_INSTANCE.ctx.console.print( rse )
		return []
