from homeassistant.const import Platform

DOMAIN = "ztm_warsaw"
REPOSITORY_URL = "https://github.com/solarssk/ztm_warsaw"

CONF_API_KEY = "api_key"
CONF_BUSSTOP_ID = "busstop_id"
CONF_BUSSTOP_NR = "busstop_nr"
CONF_LINE = "line"
CONF_DEPARTURES = "departures"  # still stored in the entry (the shape is frozen), no longer asked
NEXT_DEPARTURES = 3  # the departures after the next one that the sensor lists (Next 1 ... Next 3)
CONF_ATTRIBUTION = "Data provided by Miasto Stołeczne Warszawa and Zarząd Transportu Miejskiego (CC BY)"

# Platforms exposed by this integration
PLATFORMS = [Platform.SENSOR]