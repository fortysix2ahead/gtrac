
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import time
from datetime import timedelta
from typing import List
from typing import Optional
from typing import Tuple

from logging import getLogger

from rich.prompt import Confirm

from .activity import Activity
from .activity_types import ActivityTypes
from .config import ApplicationContext
from .config import KEY_GROUPS as GROUPS
from .ui import Choice
from .ui import diff_table2
from .utils import seconds_to_time

log = getLogger( __name__ )

DELTA = 180
MAX_DELTA = timedelta( seconds=180 )
PART_THRESHOLD = 4

@dataclass
class ActivityGroup:

	members: List[Activity] = field( default_factory=list )
	time: datetime = field( default=None )

	@property
	def head( self ) -> Activity:
		return self.members[0]

	@property
	def tail( self ) -> List[Activity]:
		return self.members[1:]

	def execute( self ):
		self.head.union( self.tail )
		for a in self.tail:
			self.head.uids.extend( a.uids )
			self.head.resources.extend( a.resources )
			for r in a.resources:
				r.__parent_activity__ = self.head
		self.head.uids = sorted( list( set( self.head.uids ) ) )

def group_activities( ctx: ApplicationContext, activities: List[Activity], force: bool = False ) -> None:
	groups = group_activities2( activities )

	for g in groups:
		updated, removed = [], []
		if force or confirm_grouping( ctx, g ):
			g.execute()
			updated.append( g.head )
			removed.extend( g.tail )

		# ctx.db.upsert_activities( updated ) # this is not necessary, activity is already updated
		ctx.db.remove_activities( removed )
		ctx.db.commit()

def group_activities2( activities: List[Activity] ) -> List[ActivityGroup]:
	last_activity, next_activity, current_group = None, None, None
	groups: List[ActivityGroup] = []
	for a in sorted( activities, key=lambda act: act.time.timestamp() ):
		last_activity, next_activity = next_activity, a
		if last_activity is None:
			current_group = ActivityGroup( members=[a], time=a.time )
			continue

		delta = next_activity.time - last_activity.time
		if delta < MAX_DELTA:
			current_group.members.append( a )
		else:
			groups.append( current_group )
			current_group = ActivityGroup( members=[a], time=a.time )

	# append the last group
	if current_group:
		groups.append( current_group )

	return [g for g in groups if len( g.members ) > 1 ]

def confirm_grouping( ctx: ApplicationContext, group: ActivityGroup, force: bool = False ) -> bool:
	if force:
		return True

	result = ctx.db.factory.dump( group.head.union( group.tail, copy=True ), Activity )
	sources = [ctx.db.factory.dump( a, Activity ) for a in group.members]

	ctx.console.print( diff_table2( result = result, sources = sources ) )

	answer = Confirm.ask( f'Continue grouping?' )
	names = sorted( list( set( [member.name for member in group.members] ) ) )
	if answer and len( names ) > 1:
		headline = 'Select a name for the new activity group:'
		choices = names
		group.head.name = Choice.ask( headline=headline, choices=choices, use_index=True, allow_free_text=True )

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
