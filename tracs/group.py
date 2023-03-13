
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from click import echo
from logging import getLogger
from rich.prompt import Confirm

from .activity import Activity
from .activity_types import ActivityTypes
from .config import ApplicationContext
from .config import KEY_GROUPS as GROUPS
from .config import console
from .ui import Choice
from .ui import diff_table2
from .utils import seconds_to_time

log = getLogger( __name__ )

DELTA = 180
PART_THRESHOLD = 4

@dataclass
class GroupResult:

	time: datetime = field( default=None )
	target: Activity = field( default=None )
	members: List[Activity] = field( default_factory=list )

@dataclass
class Bucket:

	day: int = field( default=None )
	queue: List[Activity] = field( default_factory=list )
	targets: List[GroupResult] = field( default_factory=list )

def group_activities( ctx: ApplicationContext, activities: List[Activity], force: bool = False, pretend: bool = False ) -> None:
	log.debug( f'attempting to group {len( activities )} activities' )

	changes: List[Activity] = []
	removals: List[Activity] = []
	buckets: Dict[int, Bucket] = {}

	for a in activities:
		day = int( a.time.strftime( '%y%m%d' ) )
		if not day in buckets:
			buckets[day] = Bucket( day=day )
		buckets[day].queue.append( a )

	log.debug( f'sorted activities into {len( buckets.keys() )} buckets, based on day of activity' )

	for key, bucket in buckets.items():
		log.debug( f'analysing bucket {key}' )
		if len( bucket.queue ) <= 1: # skip days with only one activity -> there's nothing to group
			continue

		for src in bucket.queue: # src means activity to be merged into a group
			# check if we find a matching target group for the ungrouped activity ua
			target = None  # target group
			for t in bucket.targets:
				delta_result, delta_time = _delta( t.time, src.time )
				if delta_result:
					target = t
					break

			# create new target group when nothing is found
			if target:
				target.members.append( src )
			else:
				bucket.targets.append( GroupResult( time=src.time, members=[ src ] ) )

	# now perform the actual (interactive) grouping
	for key, bucket in buckets.items():
		for t in bucket.targets:
			if len( t.members ) > 0:
				t.target = Activity()
				for m in t.members:
					t.target.init_from( m )
					t.target.uids.extend( m.uids )

				if force or _confirm_grouping( t ):
					changes.append( t.members[0] )
					for m in t.members[1:]:
						t.members[0].init_from( m )
						t.members[0].uids.extend( m.uids )
						removals.append( m )

	if not pretend:
		for c in changes: ctx.db.update( c )
		for r in removals: ctx.db.remove( r )

def _confirm_grouping( gr: GroupResult ) -> bool:
	echo( f"Attempting to group activities:" )

	table = diff_table2( result = as_dict( gr.target ), sources = [ as_dict( m ) for m in gr.members] )
	console.print( table )

	answer = Confirm.ask( f'Continue grouping?' )

	names = list( set( [member.name for member in [gr.target] + gr.members ] ) )
	if answer and len( names ) > 1:
		headline = 'Select a name for the new activity group:'
		choices = names
		gr.members[0].name = Choice.ask( headline=headline, choices=choices, use_index=True, allow_free_text=True )

	return answer

# ---------------------

def ungroup_activities( ctx: ApplicationContext, activities: List[Activity], force: bool = False, pretend: bool = False ) -> Optional[Tuple[List[Activity], List[Activity]]]:
	"""
	Ungroups activities
	:param ctx: context
	:param activities: groups to be ungrouped
	:param force: do not ask for permission
	:param pretend: when true does not persist changes to db
	:return:
	"""
	ungrouped_parents = []
	ungrouped_children = []
	for a in activities:
		if a.is_group:
			grouped = [ ctx.db.get( doc_id=id ) for id in a.group_for ]
			if not force:
				answer = Confirm.ask( f'Ungroup activity {a.id} ({a.name})?' )
			else:
				answer = True

			if answer:
				_ungroup( a, grouped )
				ungrouped_parents.append( a )
				ungrouped_children.extend( grouped )
				log.debug( f'ungrouped activity {a.id}' )

	# persist changes
	if not pretend:
		for a in ungrouped_parents:
			ctx.db.remove( a )
		for a in ungrouped_children:
			ctx.db.remove_field( a, GROUPS )
	else:
		return ungrouped_parents, ungrouped_children

# parting / unparting

def part_activities( activities: List[Activity], force: bool = False, pretend: bool = False, ctx: ApplicationContext = None ):
	# experimental warning ... todo: remove later
	if len( activities ) > PART_THRESHOLD:
		log.warning( f'experimental: not going to create multipart activity consisting of more than {PART_THRESHOLD} activities' )
		return

	activities.sort( key=lambda e: e.time )

	parts, gaps = [], []
	for a in activities:
		try:
			last = parts[-1]
			gap = a.time - last.time_end
			if gap.total_seconds() > 0:
				parts.append( a )
				gaps.append( seconds_to_time( gap.total_seconds() ) )
			else:
				log.warning( f'activities {a.id} and {last.id} overlap, skipping grouping as multipart' )
		except IndexError:
			parts.append( a )
			gaps.append( time( 0 ) )

	part_list = []
	for i in range( len( parts ) ):
		part_list.append( { 'gap': gaps[i].isoformat(), 'uids': parts[i].uids } )

	ctx.db.insert( Activity( parts=part_list, type=ActivityTypes.multisport, other_parts=activities ) )

def unpart_activities( activities: List[Activity], force: bool = False, pretend: bool = False, ctx: ApplicationContext = None ):
	pass

def validate_parts( activities: [Activity], force: bool ) -> bool:
	return True

# helper functions

def _delta( target_time: datetime, src_time: datetime ) -> Tuple[bool, float]:
	delta = (src_time - target_time).total_seconds()
	if -DELTA < delta < DELTA:
		return True, delta
	else:
		return False, delta

def _ungroup( parent: Activity, children: [Activity] ) -> None:
	del parent[GROUPS]
	for c in children:
		del c[GROUPS]
