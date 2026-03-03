[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/YlfKWlZ5)
# NSLP Analysis

This project processes and visualizes data sets related to analysis of the relationship between NSLP and child well-being variables.

## Setup

```bash
conda env create -f environment.yml
conda activate nslp_analysis
```

## Project Structure

```
data/
  raw-data/           # Raw data files
    shp_files/
      state/
        cb_2018_us_state_500k.cpg
        cb_2018_us_state_500k.dbf
        cb_2018_us_state_500k.prj
        cb_2018_us_state_500k.shp
        cb_2018_us_state_500k.shx
      county/
        tl_2025_us_county.cpg
        tl_2025_us_county.dbf
        tl_2025_us_county.prj
        tl_2025_us_county.shp
        tl_2025_us_county.shx
    fire.csv          # Historical fire perimeter data
    canadian_cpi.csv  # Canadian Consumer Price Index data
  derived-data/       # Filtered data and output plots
    fire_filtered.gpkg  # Fire data filtered to post-2015
    cpi_filtered.csv    # CPI data filtered to 2020 onwards
code/
  preprocessing.py    # Filters fire and CPI data
  plot_fires.py       # Plots fire perimeters
```

## Git ignore

Large raw data files are not included in this repository due to GitHub size limits.

Please download the following datasets and place them in:

data/raw-data
data/raw-data/shp_file\county

### Required Files

1. child_poverty_rate_2024.csv 
   Source: U.S. Census Bureau (ACS Table S1701 - Poverty Status in the Past 12 Months, 2024: ACS 5-Year Estimates Subject Tables)
   URL: https://data.census.gov/table/ACSST5Y2024.S1701?q=S1701:+Poverty+Status+in+the+Past+12+Months&y=2024

2. food_insecurity_2024.csv  
   Source: U.S. Census Bureau (Food Security, CPS Supplement, CSV)  
   URL: https://www.census.gov/data/datasets/time-series/demo/cps/cps-supp_cps-repwgt/cps-food-security.html

3. tl_2025_us_county.shp and other relevant files
   Source: U.S. Census Bureau 
   URL: https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/

After downloading, ensure the folder structure is:

data/
  raw-data/
    county/
        tl_2025_us_county.cpg
        tl_2025_us_county.dbf
        tl_2025_us_county.prj
        tl_2025_us_county.shp
        tl_2025_us_county.shx
    child_poverty_rate_2024.csv
    food_insecurity_2024.csv


## Usage

1. Run preprocessing to filter data:
   ```bash
   python code/preprocessing.py
   ```

2. Generate the fire perimeter plot:
   ```bash
   python code/plot_fires.py
   ```
