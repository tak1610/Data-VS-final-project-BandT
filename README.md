[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/YlfKWlZ5)
# NSLP Analysis

This project processes and visualizes data sets related to analysis of the relationship between NSLP and child well-being variables.

## Setup

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

## Project Structure

```
data/
  raw-data/           # Raw data files
    crosswalk/        # needs for MO cep data cleaning 
      ccd_sch.csv 
      EDGE_GEOCODE.xslx
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
    cash_payment_nslp.xlsx
    cep_2024.xlsx  # CEP participation rate in 2024
    child_poverty_rate_2024.csv # child poverty rate in 2024
    commodity_cost.xlsx
    Employment_Status.csv
    Food Sufficiency for Households with Children_cycle01.xlsx
    Food Sufficiency for Households with Children_cycle02.xlsx
    Food Sufficiency for Households with Children_cycle03.xlsx
    Food Sufficiency for Households with Children_cycle04.xlsx
    Food Sufficiency for Households with Children_cycle05.xlsx
    Food Sufficiency for Households with Children_cycle06.xlsx
    Food Sufficiency for Households with Children_cycle07.xlsx
    Food Sufficiency for Households with Children_cycle08.xlsx
    Food Sufficiency for Households with Children_cycle09.xlsx
    food_insecurity_2024.csv # children food insecurity data in 2024
    Household Income.csv
    Household Type 2.csv
    Household Type.csv
    pop_by_age.csv
    Population Type.csv
    total_school_lunch_served.xlsx
    voting_2000-2024.csv  # 2024 presidential election data at the county level
  derived-data/       # derived data files
    cep_county_IL.csv # CEP data in IL
    cep_county_MO.csv # CEP data in MO
    cep_school.csv # CEP data by school
    child_pov_county.csv # child poverty rate in all counties
    child_pov_il.csv # child poverty rate in IL
    child_pov_mo.csv # child poverty rate in MO
    master_state_merged.csv # master data
    master_state_with_controls.csv # master data + OLS controls
    vote_2024_il.csv #  Presidential election data in IL
    vote_2024_mo.csv # Presidential election data in MO
    vote_county_2024.csv # 2024 data for presidential election
    vote_state_2024_with_others.csv # Election data + major variables of interest
code/
  preprocessing.py    # Cleaning all the datasets
figures/
  plot1_png # state level visualization
  plot2_png # county level viulaization
writeup/
  final_project.qmd
  final_project_appendix.qmd # For OLS
  final_project.pdf
  final_project.html
  final_project_files
  
  
```

## Git ignore

Large raw data files are not included in this repository due to GitHub size limits.

Please download the following datasets and place them in:

data/raw-data
data/raw-data/shp_file/county

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

1. Run preprocessing to raw data:
   ```bash
   python code/preprocessing.py

2 Run streamlit
  streamlit run code/app.py
   ```

