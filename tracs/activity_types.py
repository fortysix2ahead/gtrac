from __future__ import annotations

from enum import Enum

class ActivityTypes( Enum ):
	aerobics = 'Aerobics'
	badminton = 'Badminton'
	ballet = 'Ballet'
	baseball = 'Baseball'
	basketball = 'Basketball'
	biathlon = 'Biathlon'
	bike = 'Cycling'
	bike_ebike = 'E-Biking'
	bike_ergo = 'Ergometer'
	bike_hand = 'Handbiking'
	bike_mountain = 'Mountain Biking'
	bike_road = 'Road Cycling'
	canoe = 'Canoe'
	climb = 'Climbing'
	crossfit = 'Crossfit'
	drive = 'Driving'
	ergo = 'Ergotrainer'
	golf = 'Golf'
	gym = 'Strength Training'
	gymnastics = 'Gymnastics'
	hiking = 'Hiking'
	ice_skate = 'Ice Skating'
	inline_skate = 'Inline Skating'
	kayak = 'Kayak'
	kitesurf = 'Kitesurf'
	multisport = 'Multisport'
	paddle = 'Paddling'
	paddle_standup = 'Standup Paddling'
	rollski = 'Roller Skiing'
	rollski_classic = 'Roller Skiing - Classic'
	rollski_free = 'Roller Skiing - Freestyle'
	row = 'Rowing'
	row_ergo = 'Rowing Ergometer'
	run = 'Run'
	run_baby = 'Run with Babyjogger'
	run_ergo = 'Treadmill Run'
	sail = 'Sailing'
	soccer = 'Soccer'
	skateboard = 'Skateboard'
	ski = 'Alpine Ski'
	snowboard = 'Snowboard'
	snowshoe = 'Snowshoe'
	swim = 'Swimming'
	swim_indoor = 'Indoor Swimming'
	swim_outdoor = 'Openwater Swimming'
	surf = 'Surfing'
	surf_wind = 'Windsurfing'
	test = 'Fitness Test'
	triathlon = 'Triathlon'
	walk = 'Walking'
	xcski = 'Cross Country Skiing'
	xcski_backcountry = 'Cross Country Skiing - Backcountry'
	xcski_classic = 'Cross Country Skiing - Classic'
	xcski_free = 'Cross Country Skiing - Freestyle'
	yoga = 'Yoga'
	other = 'Other'
	unknown = 'Unknown'

	@classmethod
	def get( cls, name: str ) -> ActivityTypes:
		try:
			return cls[name]
		except KeyError:
			return ActivityTypes.unknown

	@classmethod
	def from_str( cls, s: str ) -> ActivityTypes:
		return cls.get( s )

	@classmethod
	def to_str( cls, t: ActivityTypes ) -> str:
		return t.name

	@classmethod
	def items( cls ):
		return list( map( lambda c: (c.name, c.value), cls ) )

	@classmethod
	def names( cls ):
		return list( map( lambda c: c.name, cls ) )

	@classmethod
	def values( cls ):
		return list( map( lambda c: c.value, cls ) )

	# properties

	def __repr__( self ) -> str:
		return f'{self.name} <{self.value}>'

	def __str__( self ) -> str:
		return self.value

	@property
	def abbreviation( self ) -> str:
		return ':sports_medal:'

	@property
	def display_name( self ):
		return self.value
