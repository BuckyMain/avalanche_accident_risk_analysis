# Avalanche Accident Risk Analysis

ZHAW Data Analytics final project: link **SLF avalanche bulletins**, **IMIS snow-station measurements**, and **EnviDat accident records** to study how accident probability varies by danger level, region and weekend vs. weekday — and whether measured snow/weather data improve prediction beyond the bulletin.

## Research question

> How does the probability of an avalanche accident differ between forecasted danger levels, regions and weekends vs. weekdays, and do measured snow and weather data improve the prediction of accident days beyond the official avalanche bulletin?

## Data sources (collected by the group)

The data collection modules are located in `src/collect/`.
Each module is responsible for retrieving, caching, parsing and
standardizing data from its respective external data source.

| Python file | Data source | Purpose |
|-------------|-------------|---------|
| `accidents.py` | SLF / EnviDat CSV | Collects historical Swiss avalanche accident records since 1970, including accident locations, reported danger levels, terrain characteristics, activities and casualties. |
| `bulletin.py` | EAWS JSON archive / SLF live API | Collects historical and live avalanche bulletins, including regional danger levels, avalanche problems, critical slope aspects and elevation boundaries. |
| `holidays.py` | OpenHolidays API | Collects Swiss public holidays as an additional indicator of recreational activity and potential avalanche exposure. |
| `imis.py` | SLF IMIS Measurement API / Data Archive | Collects snow station metadata, snow depth, new snow, air temperature and wind measurements. Aggregates historical measurements into daily station-level features. |
| `regions.py` | EAWS GeoJSON | Collects Swiss avalanche warning region geometries, extracts major region identifiers and calculates geographical centroids for spatial analysis. |
| `weather.py` | Open-Meteo Archive API | Collects historical daily weather data for warning region centroids, including temperature, precipitation, snowfall, wind speed and sunshine duration. |

### Supporting utilities

| Python file | Purpose |
|-------------|---------|
| `http_utils.py` | Provides shared HTTP utilities for downloading, caching and retrying external data requests. |
| `src/paths.py` | Defines centralized project paths, storage directories, study periods and avalanche danger level mappings. |

### Data collection approach

- Automated data retrieval from external APIs and downloadable datasets.
- Local caching to reduce redundant downloads and API requests.
- Standardization of column names, data types and date formats.
- Handling of missing values and unavailable data sources.
- Temporal aggregation of weather and snow measurements.
- Spatial processing of geographical coordinates and warning regions.
- Storage of raw data in CSV, JSON and GeoJSON formats.
- Storage of processed features in Parquet format.