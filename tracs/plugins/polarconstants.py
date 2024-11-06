
from tracs.activity_types import ActivityTypes

ACCESSLINK_TYPES = {
	'AEROBICS': ActivityTypes.aerobics,  # Aerobics
	'AMERICAN_FOOTBALL': ActivityTypes.football,  # Football
	'AQUATICS': ActivityTypes.aquatics,  # Aqua fitness
	'BACKCOUNTRY_SKIING': ActivityTypes.xcski_backcountry,  # Backcountry skiing
	'BADMINTON': ActivityTypes.badminton,  # Badminton
	'BALLET_DANCING': ActivityTypes.ballet,  # Ballet
	'BALLROOM_DANCING': ActivityTypes.dancing,  # Ballroom
	'BASEBALL': ActivityTypes.baseball,  # Baseball
	'BASKETBALL': ActivityTypes.basketball,  # Basketball
	'BEACH_VOLLEYBALL': ActivityTypes.beach,  # Beach volley
	'BIATHLON': ActivityTypes.biathlon,  # Biathlon
	'BODY_AND_MIND': ActivityTypes.yoga,  # Body & Mind
	'BOOTCAMP': ActivityTypes.gym,  # Bootcamp
	'BOXING': ActivityTypes.boxing,  # Boxing
	'CIRCUIT_TRAINING': ActivityTypes.gym,  # Circuit training
	'CORE': ActivityTypes.gym,  # Core
	'CRICKET': ActivityTypes.cricket,  # Cricket
	'CROSS_TRAINER': ActivityTypes.gym,  # Cross-trainer
	'CROSS_COUNTRY_RUNNING': ActivityTypes.run,  # Cross-country running
	'CROSS-COUNTRY_SKIING': ActivityTypes.xcski,  # Skiing
	'CYCLING': ActivityTypes.bike,  # Cycling
	'CLIMBING': ActivityTypes.climb,  # Climbing
	'CURLING': ActivityTypes.curling,  # Curling
	'DANCING': ActivityTypes.dancing,  # Dancing
	'DOWNHILL_SKIING': ActivityTypes.ski,  # Downhill skiing
	'DUATHLON': ActivityTypes.duathlon,  # Duathlon
	'DUATHLON_CYCLING': ActivityTypes.bike,  # Cycling
	'DUATHLON_RUNNING': ActivityTypes.run,  # Running
	'E_BIKE': ActivityTypes.bike_ebike,  # Electric biking
	'FIELD_HOCKEY': ActivityTypes.hockey,  # Field hockey
	'FINNISH_BASEBALL': ActivityTypes.baseball_finnish,  # Finnish baseball
	'FITNESS_DANCING': ActivityTypes.dancing,  # Fitness dancing
	'FITNESS_MARTIAL_ARTS': ActivityTypes.gym,  # Fitness martial arts
	'FITNESS_STEP': ActivityTypes.gym,  # Step workout
	'FLOORBALL': ActivityTypes.floorball,  # Floorball
	'FREE_MULTISPORT': ActivityTypes.multisport,  # Multisport
	'FRISBEEGOLF': ActivityTypes.golf_disc,  # Disc golf
	'FUNCTIONAL_TRAINING': ActivityTypes.gym,  # Functional training
	'FUTSAL': ActivityTypes.futsal,  # Futsal
	'GOLF': ActivityTypes.golf,  # Golf
	'GROUP_EXERCISE': ActivityTypes.other,  # Group exercise
	'GYMNASTICK': ActivityTypes.gymnastics,  # Gymnastics
	'HANDBALL': ActivityTypes.handball,  # Handball
	'HIIT': ActivityTypes.gym,  # High-intensity interval training
	'HIKING': ActivityTypes.hiking,  # Hiking
	'ICE_HOCKEY': ActivityTypes.ice_hockey,  # Ice hockey
	'ICE_SKATING': ActivityTypes.ice_skate,  # Ice skating
	'INDOOR_CYCLING': ActivityTypes.bike_indoor,  # Indoor cycling
	'INDOOR_ROWING': ActivityTypes.row_indoor,  # Indoor rowing
	'INLINE_SKATING': ActivityTypes.inline_skate,  # Inline skating
	'JAZZ_DANCING': ActivityTypes.dancing,  # Jazz
	'JOGGING': ActivityTypes.run,  # Jogging
	'JUDO_MARTIAL_ARTS': ActivityTypes.judo,  # Judo
	'KETTLEBELL': ActivityTypes.gym,  # Kettlebell
	'KICKBOXING_MARTIAL_ARTS': ActivityTypes.kickboxing,  # Kickboxing
	'LATIN_DANCING': ActivityTypes.dancing,  # Latin
	'LES_MILLS_BARRE': ActivityTypes.gym,  # LES MILLS BARRE
	'LES_MILLS_BODYATTACK': ActivityTypes.gym,  # LES MILLS BODYATTACK
	'LES_MILLS_BODYBALANCE': ActivityTypes.gym,  # LES MILLS BODYBALANCE
	'LES_MILLS_BODYCOMBAT': ActivityTypes.gym,  # LES MILLS BODYCOMBAT
	'LES_MILLS_BODYJAM': ActivityTypes.gym,  # LES MILLS BODYJAM
	'LES_MILLS_BODYPUMP': ActivityTypes.gym,  # LES MILLS BODYPUMP
	'LES_MILLS_BODYSTEP': ActivityTypes.gym,  # LES MILLS BODYSTEP
	'LES_MILLS_CXWORKS': ActivityTypes.gym,  # LES MILLS CXWORX
	'LES_MILLS_GRIT_ATHLETIC': ActivityTypes.gym,  # LES MILLS GRIT Athletic
	'LES_MILLS_GRIT_CARDIO': ActivityTypes.gym,  # LES MILLS GRIT Cardio
	'LES_MILLS_GRIT_STRENGTH': ActivityTypes.gym,  # LES MILLS GRIT Strength
	'LES_MILLS_RPM': ActivityTypes.gym,  # LES MILLS RPM
	'LES_MILLS_SHBAM': ActivityTypes.gym,  # LES MILLS SH'BAM
	'LES_MILLS_SPRINT': ActivityTypes.gym,  # LES MILLS SPRINT
	'LES_MILLS_TONE': ActivityTypes.gym,  # LES MILLS TONE
	'LES_MILLS_TRIP': ActivityTypes.gym,  # LES MILLS TRIP
	'MOBILITY_DYNAMIC': ActivityTypes.gymnastics,  # Mobility (dynamic)
	'MOBILITY_STATIC': ActivityTypes.gymnastics,  # Mobility (static)
	'MODERN_DANCING': ActivityTypes.dancing,  # Modern
	'MOTORSPORTS_CAR_RACING': ActivityTypes.drive_road,  # Car racing
	'MOTORSPORTS_ENDURO': ActivityTypes.drive_enduro,  # Enduro
	'MOTORSPORTS_HARD_ENDURO': ActivityTypes.drive_enduro,  # Hard Enduro
	'MOTORSPORTS_MOTOCROSS': ActivityTypes.drive_cross,  # Motocorss
	'MOTORSPORTS_ROADRACING': ActivityTypes.drive_road,  # Road racing
	'MOTORSPORTS_SNOCROSS': ActivityTypes.drive_snow,  # Snocross
	'MOUNTAIN_BIKING': ActivityTypes.bike_mountain,  # Mountain biking
	'NORDIC_WALKING': ActivityTypes.walk_nordic,  # Nordic walking
	'OFFROADDUATHLON': ActivityTypes.duathlon,  # Off-road duathlon
	'OFFROADDUATHLON_CYCLING': ActivityTypes.bike,  # Mountain biking
	'OFFROADDUATHLON_RUNNING': ActivityTypes.run,  # Trail running
	'OFFROADTRIATHLON': ActivityTypes.triathlon,  # Off-road triathlon
	'OFFROADTRIATHLON_CYCLING': ActivityTypes.bike,  # Mountain biking
	'OFFROADTRIATHLON_RUNNING': ActivityTypes.run,  # Trail running
	'OFFROADTRIATHLON_SWIMMING': ActivityTypes.swim_outdoor,  # Open water swimming
	'OPEN_WATER_SWIMMING': ActivityTypes.swim_outdoor,  # Open water swimming
	'ORIENTEERING': ActivityTypes.orienteering,  # Orienteering
	'ORIENTEERING_MTB': ActivityTypes.orienteering_bike,  # Mountain bike orienteering
	'ORIENTEERING_SKI': ActivityTypes.orienteering_ski,  # Ski orienteering
	'OTHER_INDOOR': ActivityTypes.other_indoor,  # Other indoor
	'OTHER_OUTDOOR': ActivityTypes.other_outdoor,  # Other outdoor
	'PADEL': ActivityTypes.paddle,  # Padel racing
	'PARASPORTS_WHEELCHAIR': ActivityTypes.wheelchair,  # Wheelchair racing
	'PILATES': ActivityTypes.pilates,  # Pilates
	'POOL_SWIMMING': ActivityTypes.swim_indoor,  # Pool swimming
	'RIDING': ActivityTypes.ride,  # Riding
	'ROAD_BIKING': ActivityTypes.bike_road,  # Road cycling
	'ROAD_RUNNING': ActivityTypes.run,  # Road running
	'ROLLER_BLADING': ActivityTypes.roller_blade,  # Roller skating
	'ROLLER_SKIING_CLASSIC': ActivityTypes.rollski_classic,  # Classic roller skiing
	'ROLLER_SKIING_FREESTYLE': ActivityTypes.rollski_free,  # Freestyle roller skiing
	'ROWING': ActivityTypes.row,  # Rowing
	'RUGBY': ActivityTypes.rugby,  # Rugby
	'RUNNING': ActivityTypes.run,  # Running
	'SHOW_DANCING': ActivityTypes.dancing,  # Show
	'SKATEBOARDING': ActivityTypes.skateboard,  # Skateboarding
	'SKATING': ActivityTypes.inline_skate,  # Skating
	'SNOWBOARDING': ActivityTypes.snowboard,  # Snowboarding
	'SNOWSHOE_TREKKING': ActivityTypes.snowshoe,  # Snowshoe trekking
	'SOCCER': ActivityTypes.soccer,  # Soccer
	'SPINNING': ActivityTypes.spinning,  # Spinning
	'SUP': ActivityTypes.paddle_standup,  # SUP
	'SQUASH': ActivityTypes.squash,  # Squash
	'STREET_DANCING': ActivityTypes.dancing,  # Street
	'STRENGTH_TRAINING': ActivityTypes.gym,  # Strength training
	'STRETCHING': ActivityTypes.gymnastics,  # Stretching
	'SWIMMING': ActivityTypes.swim,  # Swimming
	'TABLE_TENNIS': ActivityTypes.table_tennis,  # Table tennis
	'TAEKWONDO_MARTIAL_ARTS': ActivityTypes.taekwondo,  # Taekwondo
	'TELEMARK_SKIING': ActivityTypes.telemark,  # Telemark skiing
	'TENNIS': ActivityTypes.tennis,  # Tennis
	'TRACK_AND_FIELD_RUNNING': ActivityTypes.run,  # Track&field running
	'TRAIL_RUNNING': ActivityTypes.run,  # Trail running
	'TREADMILL_RUNNING': ActivityTypes.run_ergo,  # Treadmill running
	'TRIATHLON': ActivityTypes.triathlon,  # Triathlon
	'TRIATHLON_CYCLING': ActivityTypes.bike,  # Cycling
	'TRIATHLON_RUNNING': ActivityTypes.run,  # Running
	'TRIATHLON_SWIMMING': ActivityTypes.swim_outdoor,  # Open water swimming
	'TROTTING': ActivityTypes.trotting,  # Trotting
	'ULTRARUNNING_RUNNING': ActivityTypes.run,  # Ultra running
	'VERTICALSPORTS_WALLCLIMBING': ActivityTypes.climb,  # Climbing (indoor)
	'VERTICALSPORTS_OUTCLIMBING': ActivityTypes.climb,  # Climbing (outdoor)
	'VOLLEYBALL': ActivityTypes.volleyball,  # Volleyball
	'WALKING': ActivityTypes.walk,  # Walking
	'WATER_EXERCISE': ActivityTypes.aquatics,  # Water sports
	'WATER_RUNNING': ActivityTypes.aquatics,  # Water running
	'WATERSPORTS_CANOEING': ActivityTypes.canoe,  # Canoeing
	'WATERSPORTS_KAYAKING': ActivityTypes.kayak,  # Kayaking
	'WATERSPORTS_KITESURFING': ActivityTypes.kitesurf,  # Kitesurfing
	'WATERSPORTS_SAILING': ActivityTypes.sail,  # Sailing
	'WATERSPORTS_SURFING': ActivityTypes.surf,  # Surfing
	'WATERSPORTS_WAKEBOARDING': ActivityTypes.wakeboard,  # Wakeboarding
	'WATERSPORTS_WATERSKI': ActivityTypes.waterski,  # Water skiing
	'WATERSPORTS_WINDSURFING': ActivityTypes.surf_wind,  # Windsurfing
	'XC_SKIING_CLASSIC': ActivityTypes.xcski_classic,  # Classic XC skiing
	'XC_SKIING_FREESTYLE': ActivityTypes.xcski_free,  # Freestyle XC skiing
	'YOGA': ActivityTypes.yoga,  # Yoga
}
