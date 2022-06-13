from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from click import echo
from click import style
from dateutil.tz import tzlocal
from dateutil.tz import UTC
from logging import getLogger
from questionary import confirm as qconfirm
from questionary import select as qselect
from rich import box
from rich.pretty import pretty_repr as pp
from rich.table import Table
from sys import exit as sysexit

from .activity import Activity
from .config import KEY_GROUPS as GROUPS
from .config import GlobalConfig as gc
from .config import console
from .queries import has_time
from .queries import is_group
from .queries import is_ungrouped
from .utils import fmt
from .utils import fmtl

log = getLogger( __name__ )

class Bucket:

	def __init__( self ) -> None:
		self.groups = []
		self.ungrouped = []
		self.new_groups = {}

def group_activities( activities: [Activity], force: bool = False, persist_changes: bool = True ) -> List[Tuple[Activity, List[Activity]]]:

	ungrouped: [Activity] = list( filter( is_ungrouped() & has_time(), activities ) )
	groups = gc.db.activities.search( is_group() )
	changes = []

	log.debug( f'attempting to group {len( activities )} activities' )

	buckets: Dict = {}

	for a in ungrouped:
		a: Activity = a # make a an activity ;-)
		day_str = a['time'].strftime( '%y%m%d' )
		if not day_str in buckets:
			buckets[day_str] = Bucket()
		buckets[day_str].ungrouped.append( a )

	log.debug( f'pre-sorted activities into {len( buckets.keys() )} buckets, based on day of activity' )

	for key, bucket in buckets.items():
		log.debug( f'analysing bucket {key}' )
		if len( bucket.ungrouped ) <= 1: # skip days with only one activity -> there's nothing to group
			continue

		for ua in bucket.ungrouped:
			target = None
			# check if we find a matching target group
			for group in bucket.groups:
				if _delta( group, ua )[0]:
					target = group
					break

			# create new target group when none is found
			if not target:
				new_group = Activity( init_fields=True, as_group=[ua] )
				bucket.groups.append( new_group )
				bucket.new_groups[new_group] = [ua]
			else:
				bucket.new_groups[target].append( ua )
				if GROUPS not in ua:
					ua.groups['parent'] = 0

	# now perform the actual (interactive) grouping
	for key, bucket in buckets.items():
		for parent, children in bucket.new_groups.items():
			if len( children ) > 1:
				do_grouping = True if force else _ask_for_join( parent, children )

				if do_grouping:
					_group( parent, children )
					parent['name'] = _ask_for_name( children, force )
					parent['type'] = _ask_for_type( children, force )
					changes.append( (parent, children) )

				log.debug( f'grouped activities {fmtl( children )}' )

	if persist_changes:
		for parent, children in changes:
			doc_id = gc.db.insert( parent )
			for c in children:
				c.groups['parent'] = doc_id
				gc.db.update( c )
	else:
		return changes

def _ask_for_join( parent: Activity, children: [Activity] ) -> bool:
	echo( f"Attempting to group activities {fmtl( children )}" )

	delta = 0.0

	if delta >= 60.0 or delta <= -60.0:
		delta_str = style( f'{delta} sec', fg='red', bold=True )
	elif -60.0 < delta < 60.0:
		delta_str = style( f'{delta} sec', fg='blue', bold=True )
	else:
		delta_str = style( f'{delta} sec', fg='green', bold=True )

#	et_diff = [children[0].duration - c.duration for c in children]

	table = Table( box=box.MINIMAL, show_header=False, show_footer=False )

	data = [
		['Id', *[c['id'] for c in children] ],
		['Uid', *[c['uid'] for c in children] ],
#		['Raw Id', *[c['raw_id'] for c in children] ],
		['Service', *[c['service'] for c in children] ],
		['Name', *[c['name'] for c in children] ],
		['Type', *[fmt( c['type'] ) for c in children] ],
#		['URL', source.url, target.url],
		['Local Time', *[fmt( c['localtime'] ) for c in children]],
		['UTC Time', *[fmt( c['time'] ) for c in children]],
		['Datetime Delta', *[f"\u00B1{fmt( c['time'] - children[0]['time'] )}" for c in children]],
		#		['Datetime', *[f'{fmt_delta(c.utctime, children[0].utctime)}' for c in children]],
		['Elapsed Time', *[fmt( c['duration'] ) for c in children]],
		['Distance', *[fmt( c['distance'] ) for c in children]],
	]

	for d in data:
		table.add_row( *[ pp( item ) for item in d ] )

	console.print( table )

	# source_time = time_str( source.activity.localtime, app.cfg )
	# target_time = time_str( target.activity.localtime, app.cfg )
	# if source_time == target_time:
	# 	data.append( ['Start Time (local)', source_time, target_time] )
	# else:
	# 	data.append( ['Start Time (local)', style( source_time, fg='red' ), style( target_time, fg='red' )] )
	#
	# if tz_correction:
	# 	data.append( ['Start Time Delta', style( f'{delta} sec (assuming that one timezone is incorrect)', fg='red' )] )
	# else:
	# 	data.append( ['Start Time Delta', delta_str ] )
	#

	answer = qconfirm( f'Continue grouping?', default=False, qmark='', auto_enter=True ).ask()
	if answer is None:
		sysexit(-1)
	else:
		return answer

def _ask_for_name( children: [Activity], force: bool ) -> str:
	if not force:
		names = sorted( { *[c['name'] for c in children] } )
		if len( names ) > 1:
			answer = qselect(
				'Which name should be used for the grouped activity?',
				choices=names,
				qmark='',
				use_shortcuts=True
			).ask()

			if answer is None:
				sysexit( -1 )
			else:
				return answer
		else:
			return names[0]
	else:
		return children[0]['name']

def _ask_for_type( children: [Activity], force: bool ) -> str:
	if not force:
		types = sorted( { *[c['type'] for c in children] } )
		if len( types ) > 1:
			answer = qselect(
				'Which type should be used for the grouped activity?',
				choices=types,
				qmark='',
				use_shortcuts=True
			).ask()

			if answer is None:
				sysexit( -1 )
			else:
				return answer
		else:
			return types[0]
	else:
		return children[0]['type']

# ---------------------

def ungroup_activities( activities: [Activity], force: bool, persist_changes = True ) -> Optional[Tuple[List[Activity], List[Activity]]]:
	"""
	Ungroups activities
	:param activities: groups to be ungrouped
	:param force: do not ask for permission
	:param persist_changes: when true does not persist changes to db, instead return changed activities
	:return:
	"""
	ungrouped_parents = []
	ungrouped_children = []
	for a in activities:
		if a.is_group:
			grouped = [ gc.db.get( doc_id=id ) for id in a.group_for ]
			if not force:
				answer = qconfirm( f'Ungroup activity {a.id} ({a.name})?', default=False, qmark='', auto_enter=True ).ask()
			else:
				answer = True

			if answer:
				_ungroup( a, grouped )
				ungrouped_parents.append( a )
				ungrouped_children.extend( grouped )
				log.debug( f'ungrouped activity {a.id}' )

	# persist changes
	if persist_changes:
		for a in ungrouped_parents:
			gc.db.remove( a )
		for a in ungrouped_children:
			gc.db.remove_field( a, GROUPS )
	else:
		return ungrouped_parents, ungrouped_children

# parting / unparting

def part_activities( activities: [Activity], force: bool ):
	if validate_parts( activities ) or force:
		pass

def unpart_activities( activities: [Activity], force: bool ):
	pass

def validate_parts( activities: [Activity], force: bool ) -> bool:
	return True

# helper functions

def _delta( group: Activity, ungrouped: Activity ) -> Tuple[bool, float, bool]:
	delta = (ungrouped.utctime - group.utctime).total_seconds()
	# delta 2/3: assume that one activity reports localtime as UTC
	delta2 = (ungrouped.utctime - group.utctime.replace( tzinfo=tzlocal() ).astimezone( UTC )).total_seconds()
	delta3 = (ungrouped.utctime.replace( tzinfo=tzlocal() ).astimezone( UTC ) - group.utctime).total_seconds()
	if -60 < delta < 60:
		return True, delta, False
	elif (-60 < delta2 < 60) or (-60 < delta3 < 60):
		delta = delta2 if abs( delta2 ) < abs( delta3 ) else delta3
		return True, delta, True
	else:
		return False, delta, False

def _group( parent: Activity, children: [Activity] ) -> None:
	parent.groups['ids'] = list( [c.doc_id for c in children] )
	parent.groups['uids'] = list( [c['uid'] for c in children] )
	for c in children:
		c.groups['parent'] = parent.doc_id

def _ungroup( parent: Activity, children: [Activity] ) -> None:
	del parent[GROUPS]
	for c in children:
		del c[GROUPS]