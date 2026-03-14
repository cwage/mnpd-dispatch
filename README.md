# mnpd-dispatch

CLI tool and API for querying Nashville Metro Police Department (MNPD) and Nashville Fire Department (NFD) active dispatch data by address proximity.

Uses the public ArcGIS feeds from [data.nashville.gov](https://data.nashville.gov) — no API key required.

## Requirements

- Docker & Docker Compose
- `jq` (for the CLI script)
- `curl`

## Quick Start

```bash
# Start the API
docker compose up -d

# Query dispatches near an address
./mnpd-dispatch.sh -a '600 Broadway, Nashville, TN'

# Wider radius
./mnpd-dispatch.sh -a '600 Broadway, Nashville, TN' -r 5

# Include fire department dispatches
./mnpd-dispatch.sh -a '600 Broadway, Nashville, TN' -f -r 3

# List all active dispatches
./mnpd-dispatch.sh -l
```

## CLI Usage

```
Usage: ./mnpd-dispatch.sh -a <address> [-r <radius>] [-f]
       ./mnpd-dispatch.sh -l

Options:
  -a <addr>    Search near this address (required for proximity search)
  -r <miles>   Search radius in miles (default: 2)
  -f           Include fire department dispatches
  -l           List all active dispatches (no proximity filter)
```

Output includes incident type, address, area, time received, distance from your search address, and a Google Maps directions link.

## Example Output

```
═══════════════════════════════════════════════════════
  DISPATCHES NEAR: 600 Broadway, Nashville, TN
  Radius: 3 mi | Found: 2
═══════════════════════════════════════════════════════
───────────────────────────────────────────────────────
  MNPD                 SHOTS FIRED
  Code:                83P

  Address:          2009 SEVIER ST
  Area:             SHELBY PARK

  Received:         2026-03-14 06:05:03 PM CDT (20m ago)

  Distance:         2.43 miles
  Map:              https://www.google.com/maps/dir/...

═══════════════════════════════════════════════════════
```

## Data Sources

- **MNPD Active Dispatch** — updates ~every 15 minutes, includes incident type, address, and area/neighborhood
- **NFD Active Incidents** — updates ~every 5 minutes, includes incident type and ZIP code (no street address)

Dispatch addresses are geocoded via the [US Census Geocoder](https://geocoding.geo.census.gov/geocoder/) to calculate distance. Results are cached in memory for the lifetime of the container.

## License

MIT
