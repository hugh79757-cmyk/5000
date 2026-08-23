# ETAP Family Map — 36 blogs → Writers/Collectors/Sources

Generated: 2026-08-21, total 36 blogs, 13 families

| Family | Members | Writer | Collector | Source | DB Tables | Representative (max posts) | Status |
|--------|---------|--------|-----------|--------|-----------|---------------------------|--------|
| F1 | 10: foodtour-hugo, luxury-hugo, citytours-hugo, watertours-hugo, hiking-hugo, escape-hugo, extreme-hugo, nightlife-hugo, ghost-hugo, layover-hugo | `pipelines/etap/foodtour_writer.py` | viator_api | Viator | viator_tours, city_aliases | **foodtour-hugo (142)** | active |
| F2 | 8: adventure-hugo, culture-hugo, multiday-hugo, tour-hugo, tours-hugo, transfers-hugo, walking-hugo, watersports-hugo | `pipelines/etap/pipeline.py` | viator_api | Viator | viator_tours | **tour-hugo (254)** | active |
| F3 | 4: bus-hugo, eurail-hugo, ferry-hugo, trains-hugo | `pipelines/etap/eurail_writer.py` | omio | Omio | omio_routes | **eurail-hugo (170)** | active |
| F4 | 4: cruise-hugo, daytrips-hugo, nature-hugo, phototour-hugo | `pipelines/etap/daytrips_writer.py` | viator_api | Viator (tours+dest) | viator_destinations, viator_tours | **daytrips-hugo (182)** | active |
| F5 | 2: visa-hugo, visafree-hugo | `pipelines/etap/visa_writer.py` | visa | Visa DB | visa_requirements, visa_requirements | **visa-hugo (252)** | active |
| F6 | 1: airlines-hugo | `pipelines/etap/airlines_writer.py` | aviasales/reference | Aviasales+Ref | ref_airports, ref_airlines | **airlines-hugo (115)** | active |
| F7 | 1: airports-hugo | `pipelines/etap/airports_writer.py` | aviasales/reference | Aviasales+Ref | ref_airports, airline_routes | **airports-hugo (163)** | paused |
| F8 | 1: deals-hugo | `pipelines/etap/deals_writer.py` | aviasales | Aviasales | ref_airports, flight_prices | **deals-hugo (105)** | active |
| F9 | 1: dining-hugo | `pipelines/etap/dining_writer.py` | reference | Michelin DB | michelin_restaurants, city_aliases | **dining-hugo (119)** | active |
| F10 | 1: esim-hugo | `pipelines/etap/esim_writer.py` | airalo | Airalo | airalo_esim | **esim-hugo (265)** | active |
| F11 | 1: flights-hugo | `pipelines/etap/flight_writer.py` | aviasales | Aviasales | flight_prices, flight_direct | **flights-hugo (272)** | active |
| F12 | 1: michelin-hugo | `pipelines/etap/michelin_writer.py` | reference | Michelin DB | michelin_restaurants | **michelin-hugo (272)** | active |
| F13 | 1: nomad-hugo | `pipelines/etap/nomad_writer.py` | visa | Visa DB | airalo_esim, visa_requirements | **nomad-hugo (39)** | paused |

## Notes
- Families grouped by (primary DB table, collector module, external source). Same group shares writer logic.
- Representative = most posts (local count).
- tour-hugo has no dedicated writer, fallback to pipelines/etap/pipeline.py.