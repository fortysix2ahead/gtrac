from __future__ import annotations

from enum import Enum

class ActivityTypes( Enum ):
	aerobics = 'Aerobics'
	aquatics = 'Aquatics'
	badminton = 'Badminton'
	ballet = 'Ballet'
	baseball = 'Baseball'
	baseball_finnish = 'Finnish Baseball' # WTF is that???
	basketball = 'Basketball'
	beach = 'Beach Volleyball'
	biathlon = 'Biathlon'
	bike = 'Cycling'
	bike_ebike = 'E-Biking'
	bike_ergo = 'Ergometer'
	bike_hand = 'Handbiking'
	bike_indoor = 'Indoor Cycling'
	bike_mountain = 'Mountain Biking'
	bike_road = 'Road Cycling'
	boxing = 'Boxing'
	canoe = 'Canoe'
	climb = 'Climbing'
	cricket = 'Cricket'
	crossfit = 'Crossfit'
	curling = 'Curling'
	dancing = 'Dancing'
	drive = 'Driving'
	drive_cross = 'Motocross'
	drive_enduro = 'Enduro'
	drive_road = 'Car Racing'
	drive_snow = 'Snowcross'
	duathlon = 'Duathlon'
	ergo = 'Ergotrainer'
	football = 'American Football'
	floorball = 'Floorball'
	futsal = 'Futsal'
	golf = 'Golf'
	golf_disc = 'Disc Golf'
	gym = 'Strength Training'
	gymnastics = 'Gymnastics'
	handball = 'Handball'
	hiking = 'Hiking'
	hockey = 'Hockey'
	ice_hockey = 'Ice Hockey'
	ice_skate = 'Ice Skating'
	inline_skate = 'Inline Skating'
	judo = 'Judo'
	kayak = 'Kayak'
	kickboxing = 'Kickboxing'
	kitesurf = 'Kitesurf'
	multisport = 'Multisport'
	orienteering = 'Orienteering'
	orienteering_bike = 'Mountain Bike Orienteering'
	orienteering_ski = 'Ski Orienteering'
	paddle = 'Paddling'
	paddle_standup = 'Standup Paddling'
	pilates = 'Pilates'
	ride = 'Riding'
	roller_blade = 'Roller Blading'
	rollski = 'Roller Skiing'
	rollski_classic = 'Roller Skiing - Classic'
	rollski_free = 'Roller Skiing - Freestyle'
	row = 'Rowing'
	row_ergo = 'Rowing Ergometer'
	row_indoor = 'Indoor Rowing'
	rugby = 'Rugby'
	run = 'Run'
	run_baby = 'Run with Babyjogger'
	run_ergo = 'Treadmill Run'
	sail = 'Sailing'
	soccer = 'Soccer'
	skateboard = 'Skateboard'
	ski = 'Alpine Ski'
	snowboard = 'Snowboard'
	snowshoe = 'Snowshoe'
	spinning = 'Spinning'
	squash = 'Squash'
	swim = 'Swimming'
	swim_indoor = 'Indoor Swimming'
	swim_outdoor = 'Openwater Swimming'
	surf = 'Surfing'
	surf_wind = 'Windsurfing'
	table_tennis = 'Table Tennis'
	taekwondo = 'Taekwondo'
	telemark = 'Telemark Skiing'
	tennis = 'Tennis'
	test = 'Fitness Test'
	triathlon = 'Triathlon'
	trotting = 'Trotting'
	volleyball = 'Volleyball'
	wakeboard = 'Wakeboarding'
	walk = 'Walking'
	walk_nordic = 'Nordic Walking'
	waterski = 'Water Skiing'
	wheelchair = 'Wheelchair'
	xcski = 'Cross Country Skiing'
	xcski_backcountry = 'Cross Country Skiing - Backcountry'
	xcski_classic = 'Cross Country Skiing - Classic'
	xcski_free = 'Cross Country Skiing - Freestyle'
	yoga = 'Yoga'
	other = 'Other'
	other_indoor = 'Other Indoor'
	other_outdoor = 'Other Outdoor'
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
