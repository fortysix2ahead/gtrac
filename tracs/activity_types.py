
from __future__ import annotations

from enum import Enum

class ActivityTypes( Enum ):

	aerobics = 'aerobics'
	badminton = 'badminton'
	ballet = 'ballet'
	baseball = 'baseball'
	basketball = 'basketball'
	biathlon = 'biathlon'
	bike = 'bike'
	bike_ebike = 'bike_ebike'
	bike_ergo = 'bike_ergo'
	bike_hand = 'bike_hand'
	bike_mountain = 'bike_mountain'
	bike_road = 'bike_road'
	canoe = 'canoe'
	climb = 'climb'
	crossfit = 'crossfit'
	drive = 'drive'
	ergo = 'ergo'
	golf = 'golf'
	gym = 'gym'
	gymnastics = 'gymnastics'
	hike = 'hiking'
	ice_skate = 'ice_skate'
	inline_skate = 'inline_skate'
	kayak = 'kayak'
	kitesurf = 'kitesurf'
	multisport = 'multisport'
	paddle = 'paddle'
	paddle_standup = 'paddle_standup'
	rollski = 'rollski'
	rollski_classic = 'rollski_classic'
	rollski_free = 'rollski_free'
	row = 'row'
	row_ergo = 'row_ergo'
	run = 'run'
	run_baby = 'run_baby'
	run_ergo = 'run_ergo'
	sail = 'sail'
	soccer = 'soccer'
	skateboard = 'soccer'
	ski = 'ski'
	snowboard = 'snowboard'
	snowshoe = 'snowshoe'
	swim = 'swim'
	swim_indoor = 'swim_indoor'
	swim_outdoor = 'swim_outdoor'
	surf = 'surf'
	surf_wind = 'surf_wind'
	test = 'test'
	triathlon = 'triathlon'
	walk = 'walk'
	xcski = 'xcski'
	xcski_backcountry = 'xcski_backcountry'
	xcski_classic = 'xcski_classic'
	xcski_free = 'xcski_free'
	yoga = 'yoga'
	other = 'other'
	unknown = 'unknown'

	@classmethod
	def get( cls, value: str ) -> ActivityTypes:
		for item in cls.items():
			if item[1] == value:
				return cls[item[0]]
		return cls['unknown']

	@classmethod
	def from_str( cls, s: str ) -> ActivityTypes:
		return cls.get( s )

	@classmethod
	def to_str( cls, t: ActivityTypes ) -> str:
		return t.value

	@classmethod
	def items( cls ):
		return list( map( lambda c: (c.name, c.value), cls ) )

	@classmethod
	def names( cls ):
		return list( map( lambda c: c.name, cls ) )

	@classmethod
	def values( cls ):
		return list( map( lambda c: c.value, cls ) )

	@property
	def abbreviation( self ) -> str:
		return ':sports_medal:'

	@property
	def display_name( self ):
		return display_names.get( self, ActivityTypes.unknown )

display_names = {
	ActivityTypes.aerobics: 'Aerobics',
	ActivityTypes.badminton: 'Badminton',
	ActivityTypes.ballet: 'Ballet',
	ActivityTypes.baseball: 'Baseball',
	ActivityTypes.basketball: 'Basketball',
	ActivityTypes.biathlon: 'Biathlon',
	ActivityTypes.bike: 'Cycling',
	ActivityTypes.bike_ebike: 'E-Biking',
	ActivityTypes.bike_ergo: 'Ergometer',
	ActivityTypes.bike_hand: 'Handbiking',
	ActivityTypes.bike_mountain: 'Mountain Biking',
	ActivityTypes.bike_road: 'Road Cycling',
	ActivityTypes.canoe: 'Canoe',
	ActivityTypes.climb: 'Climbing',
	ActivityTypes.crossfit: 'Crossfit',
	ActivityTypes.drive: 'Driving',
	ActivityTypes.ergo: 'Ergotrainer',
	ActivityTypes.golf: 'Golf',
	ActivityTypes.gym: 'Strength Training',
	ActivityTypes.gymnastics: 'Gymnastics',
	ActivityTypes.hike: 'Hiking',
	ActivityTypes.ice_skate: 'Ice Skating',
	ActivityTypes.inline_skate: 'Inline Skating',
	ActivityTypes.kayak: 'Kayak',
	ActivityTypes.kitesurf: 'Kitesurf',
	ActivityTypes.multisport: 'Multisport',
	ActivityTypes.paddle: 'Paddling',
	ActivityTypes.paddle_standup: 'Standup Paddling',
	ActivityTypes.rollski: 'Roller Skiing',
	ActivityTypes.rollski_classic: 'Roller Skiing - Classic',
	ActivityTypes.rollski_free: 'Roller Skiing - Freestyle',
	ActivityTypes.row: 'Rowing',
	ActivityTypes.row_ergo: 'Rowing Ergometer',
	ActivityTypes.run: 'Run',
	ActivityTypes.run_baby: 'Run with Babyjogger',
	ActivityTypes.run_ergo: 'Treadmill Run',
	ActivityTypes.sail: 'Sailing',
	ActivityTypes.soccer: 'Soccer',
	ActivityTypes.skateboard: 'Skateboard',
	ActivityTypes.ski: 'Alpine Ski',
	ActivityTypes.snowboard: 'Snowboard',
	ActivityTypes.snowshoe: 'Snowshoe',
	ActivityTypes.swim: 'Swimming',
	ActivityTypes.swim_indoor: 'Indoor Swimming',
	ActivityTypes.swim_outdoor: 'Openwater Swimming',
	ActivityTypes.surf: 'Surfing',
	ActivityTypes.surf_wind: 'Windsurfing',
	ActivityTypes.test: 'Fitness Test',
	ActivityTypes.triathlon: 'Triathlon',
	ActivityTypes.walk: 'Walking',
	ActivityTypes.xcski: 'Cross Country Skiing',
	ActivityTypes.xcski_backcountry: 'Cross Country Skiing - Backcountry',
	ActivityTypes.xcski_classic: 'Cross Country Skiing - Classic',
	ActivityTypes.xcski_free: 'Cross Country Skiing - Freestyle',
	ActivityTypes.yoga: 'Yoga',
	ActivityTypes.other: 'Other',
	ActivityTypes.unknown: 'Unknown',
}
