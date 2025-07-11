# ------------------------------------- #
# name   : 01-tidy/01-disease
# purpose: this script ...
#
# imports:
#   - `10-data/01-source/ihme/disease/ihme_data.csv`
#     - Institute for Health Metrics and Evaluation, Global Burden of Disease
#       Study 2019 data
#   - `10-data/02-tidy/00-panel.rds`
#     - tidy panel of countries with spatial geometry
#       Exported from `20-scripts/01-tidy/00-panel/default.R`
#
# exports:
#   - `10-data/02-tidy/01-disease.rds`
#      - tidied ihme disease data with pnid panel identifier for merging
#
# sections:
#     0 - setup
#     1 - tidy panel
#     2 - tidy data
#     3 - merge
#     4 - save


# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(lubridate)
library(sf)
library(countrycode)

library(here)
i_am("20-scripts/01-tidy/01-disease.R")

# load data
ihme <- read_csv(here("10-data/01-source/ihme/disease/ihme_data.csv"),
                 show_col_types = F)
pnl  <- read_rds(here("10-data/02-tidy/00-panel.rds"))

# load functions
source(here("20-scripts/01-tidy/fn-gencc.R"))


# ------------------------------------- #
# 1 - tidy panel ----
# retain only id to avoid variable duplication
pnl <- pnl %>%
  st_drop_geometry %>%
  as_tibble %>%
  select(pnid)


# ------------------------------------- #
# 2 - tidy ihme ----
ihme <- ihme %>%
  mutate(cause = case_match(
    cause,
    "Sexually transmitted infections excluding HIV" ~ "sti",
    "Respiratory infections and tuberculosis"       ~ "respinf",
    "HIV/AIDS"                                      ~ "hiv",
    "Measles"                                       ~ "measles",
    "Tuberculosis"                                  ~ "tb",
    "Malaria"                                       ~ "malaria",
    .default = NA_character_)) %>%
  drop_na(cause) %>%
  filter(measure == "Incidence",
         metric  == "Number") %>%
  pivot_wider(.,
              id_cols      = c(location, year),
              names_from   = cause,
              names_prefix = "ihme_",
              values_from  = val) %>%
  janitor::clean_names() %>%
  rename(cname = location) %>%
  gencc %>%
  mutate(pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, starts_with("ihme"))


# ------------------------------------- #
# 3 - merge ----
res <- list(pnl, ihme) %>%
  purrr::reduce(., left_join, by = "pnid") %>%
  drop_na(ihme_hiv)

rm(ihme, pnl, gencc)


# ------------------------------------- #
# 4 - save ----
write_rds(res, file = here("10-data/02-tidy/01-disease.rds"))
rm(list=ls())
