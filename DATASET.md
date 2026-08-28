# Dataset Notes

This project uses scheduled GTFS timetable data, not live train positions. The local feed folders were downloaded from the [gtfs.de feed catalogue](https://gtfs.de/en/feeds/).

Currently used feeds:

- `Long Distance Rail Germany`
- `Regional Rail Germany`

The GTFS interpretation below is based on the official [GTFS Schedule Reference](https://gtfs.org/documentation/schedule/reference/) and the [GTFS Schedule Best Practices](https://gtfs.org/documentation/schedule/schedule-best-practices/). The reference is the stricter field-by-field source; the best-practices page is useful for validating modelling assumptions.

## Files Used

| File                   | Role in this project                                                                                                                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stops.txt`          | Provides stop IDs, names, and coordinates. Stops can represent stations, platforms, or boarding points, so one real station may appear as multiple stop records.                                        |
| `routes.txt`         | Provides the service or line identity. This project uses`route_id` to estimate route diversity and `route_short_name` to infer rail categories such as regional, S-Bahn, intercity, and high-speed. |
| `trips.txt`          | Provides individual scheduled train runs. A trip is more specific than a route, so`trip_id` is used for active train-movement counts.                                                                 |
| `stop_times.txt`     | Provides the ordered stop sequence and arrival/departure times for each trip. This drives timestamp frames, animation interpolation, and station stop-event counts.                                     |
| `calendar.txt`       | Defines regular weekly service patterns and their valid date ranges.                                                                                                                                    |
| `calendar_dates.txt` | Adds or removes service on specific dates. This is applied together with`calendar.txt` when selecting active trips.                                                                                   |
| `shapes.txt`         | Would provide route geometry for realistic path interpolation. The current local feeds do not include it, so the project uses stop-to-stop interpolation.                                               |

## Working Interpretation

```text
route = service identity or line grouping
trip = one scheduled train run
stop = station, stop, platform, or boarding point
stop_time = one visit of one trip to one stop at a specific time
service_id = tells whether the trip is active on the chosen date
shape = geographic path geometry for drawing the trip
```
