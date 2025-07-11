# ------------------------------------- #
# name   : 01-tidy/00-panel
# purpose: this script creates a country panel for disease-trade analysis using
#          Weidmann's `cshapes` package.
#
# exports:
#   - `10-data/02-tidy/00-panel.rds`
#      - correct panel of all valid countries between 1998-2019 (inclusive)
#      - valid here meaning appropriate country creation year
#
# sections:
#     0 - setup
#     1 - extract cshapes
#     2 - project full panel into Mollweide Equal Area
#     3 - tidy panel
#     4 - save

# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(sf)
library(cshapes)
library(countrycode)

library(here)
i_am("20-scripts/01-tidy/00-panel/default.R")

# load functions
source(here("20-scripts/01-tidy/00-panel/fn-tidy_cshape_year.R"))


# ------------------------------------- #
# 1 - extract cshapes ----
res <- lapply(1998:2019, tidy_cshape_year) %>% bind_rows %>% arrange(ccode, year)
rm(tidy_cshape_year)


# ------------------------------------- #
# 2 - project panel ----
# Project - **Mollweide** equal area ([https://projectionwizard.org/](#0))
res <- res %>%
  st_transform(
    .,
    crs = st_crs("+proj=moll +lon_0=0 +datum=WGS84 +units=km +no_defs")
    ) %>%
  mutate(area_sqkm = as.numeric(st_area(.))) %>%
  select(pnid, area_sqkm) %>%
  st_drop_geometry() %>%
  left_join(res, ., by = "pnid")


# ------------------------------------- #
# 3 - tidy panel ----
# Create id labels and assign to data frame row names. Needed for spatial
# weights later
rownames(res) <- res$id.pnid


# ------------------------------------- #
# 4 - save ----
write_rds(res, file = here("10-data/02-tidy/00-panel.rds"))
rm(list = ls())

