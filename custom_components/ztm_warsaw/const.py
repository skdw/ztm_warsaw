"""The names and constants shared by the whole integration: the domain, the keys of the entry's data, the platforms."""

from homeassistant.const import Platform

DOMAIN = "ztm_warsaw"
REPOSITORY_URL = "https://github.com/solarssk/ztm_warsaw"

CONF_API_KEY = "api_key"
CONF_BUSSTOP_ID = "busstop_id"
CONF_BUSSTOP_NR = "busstop_nr"
CONF_LINE = "line"
CONF_DEPARTURES = "departures"  # still stored in the entry (the shape is frozen), no longer asked
CONF_WALKING_TIME = "walking_time"  # minutes from the user to the stop, kept in the data of the stop (0: no walking time)
MAX_WALKING_TIME = 120
NEXT_DEPARTURES = 3  # the departures after the next one that the sensor lists (Next 1 ... Next 3)
CONF_ATTRIBUTION = "Data provided by Miasto Stołeczne Warszawa and Zarząd Transportu Miejskiego (CC BY)"

# Platforms exposed by this integration
KEY_PORTAL_URL = "https://dane.um.warszawa.pl/pl/key-api"  # where the City gives a token of the new API
PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]