# Facility context data (read-only)

`osm_gppd_facilities.parquet` -- 72,624 named facility records (columns: facility_id, lat, lon, facility_type, source, name, country),
from OpenStreetMap (`landuse=industrial` areas and tagged industrial features) and the WRI Global Power Plant Database (GPPD).
Imported from the earlier OrbiFlare prototype; no records were added, edited or invented.

Used by `backend/app/context/facilities.py` as a **spatial context source** (nearest / nearby lookup), never as a label and never as
training data. Only facilities that a live event actually references are copied into the operational `facilities` table.

Handling rules
* Bounding box: India (68,6,98,37) -- 39,663 records.
* Excluded from *thermal-source* context: GPPD `Solar`, `Wind`, `Hydro` (no combustion heat source a VIIRS pixel could see).
* OSM areas are stored as a single point, so distances are to that point, not to the area boundary.
* OSM/GPPD are incomplete. Absence of a nearby facility is not evidence of a natural fire.
