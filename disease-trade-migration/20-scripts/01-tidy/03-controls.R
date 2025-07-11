# ------------------------------------- #
# name   : 01-tidy/03-controls
# purpose: this script tidies UN, WHO, and IHME covariate data and exports
#
# imports:
#   - `10-data/01-source/un/un-pop.csv`
#     - country population estimates from UN
#   - `10-data/01-source/un/un-gdp.csv`
#     - country GDP estimates from UN
#   - `10-data/01-source/ihme/health_spending/ihme_health_spend_1995-2018.csv`
#     - health spending (private and public) from IHME
#   - `10-data/01-source/other/wb-indicators.csv`
#     - World Bank development indicators
#   - `10-data/01-source/other/wb-indicators2.csv`
#     - World Bank development indicators
#   - `10-data/01-source/cepii_gravity/gravity_v202102.Rds`
#     - CEPII data
#   - `10-data/01-source/un/un_int-migrant-stock.xlsx`
#     - international migrant stocks and flows from UN
#   - `10-data/02-tidy/00-panel.rds`
#     - tidy panel of countries with spatial geometry
#       Exported from `20-scripts/01-tidy/00-panel/default.R`
#
# exports:
#   - `10-data/02-tidy/spatial-weights/03-controls.rds`
#      - tidy panel of control variables
#   - `10-data/02-tidy/03-migration.rds`
#      - tidy dyadic panel of migration stock and flows from UN. Used to
#        construct migration spatial weights matrices
#
# sections:
#     0 - setup
#     1 - tidy panel
#     2 - tidy data
#     3 - merge data
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
library(readxl)
library(imputeTS)

library(here)
i_am("20-scripts/01-tidy/03-controls.R")

# load data
unpop <- read_csv(here("10-data/01-source/un/un-pop.csv"), show_col_types = F)
ungdp <- read_csv(here("10-data/01-source/un/un-gdp.csv"), show_col_types = F)
ihme  <- read_csv(
  here("10-data/01-source/ihme/health_spending/ihme_health_spend_1995-2018.csv"),
  show_col_types = F)
wdi1  <- read_csv(here("10-data/01-source/other/wb-indicators.csv"),
                  na = "..",
                  show_col_types = F)
wdi2  <- read_csv(here("10-data/01-source/other/wb-indicators2.csv"),
                  na = "..",
                  show_col_types = F)
cep   <- read_rds(here("10-data/01-source/cepii_gravity/gravity_v202102.Rds"))
migr  <- read_xlsx(here("10-data/01-source/un/un_int-migrant-stock.xlsx"),
                   sheet = 2)
pnl   <- read_rds(here("10-data/02-tidy/00-panel.rds"))
# load functions
source("20-scripts/01-tidy/fn-gencc.R")


# ------------------------------------- #
# 1 - tidy panel ----
# retain only id to avoid variable duplication
pnl <- pnl %>%
  st_drop_geometry %>%
  as_tibble %>%
  select(pnid)


# ------------------------------------- #
# 2 - tidy data ----

## -------------- ##
## UN - population ----
unpop <- unpop %>%
  janitor::clean_names() %>%
  filter(year < 2022) %>%
  rename(cname = location) %>%
  gencc %>%
  rename(popMale     = pop_male,
         popFemale   = pop_female,
         popTotal    = pop_total,
         popDensSqkm = pop_density) %>%
  mutate(across(.cols = c(popMale, popFemale, popTotal),
                .fns  = ~.x * 1e3),
         pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, starts_with("pop")) %>%
  drop_na() %>% # Vatican city
  rename_with(.data = .,
              .cols = !pnid,
              .fn   = ~paste0("un_", .x))

## -------------- ##
## UN - GDP ----
ungdp <- ungdp %>%
  mutate(cls = case_match(IndicatorName,
                          "Gross Domestic Product (GDP)"  ~ "gdpUSD",
                          "Exports of goods and services" ~ "exportsUSD",
                          "Imports of goods and services" ~ "importsUSD",
                          .default = NA_character_),
         cname = case_when(
           str_detect(Country, "Ivoire") ~ "Ivory Coast",
           .default = stringi::stri_trans_general(Country,"latin-ascii"))) %>%
  gencc %>%
  select(-CountryID, -Country, -IndicatorName, -cname) %>%
  pivot_longer(.,
               cols      = !c(ccode, cls),
               names_to  = "year",
               values_to = "val") %>%
  filter(year >= 2000, !is.na(val)) %>%
  # Assuming 1 year (Sierra Leone 2919) negative exports a typo
  mutate(val = abs(val)) %>%
  group_by(ccode, year, cls) %>%
  summarize(val = sum(val), .groups = "keep") %>%
  ungroup %>%

  pivot_wider(.,
              id_cols      = c(ccode, year),
              names_from   = cls,
              names_prefix = "un_",
              values_from  = val) %>%

  mutate(pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, starts_with("un_"))

## -------------- ##
## WB1 ----
wdi1 <- wdi1 %>%
  janitor::clean_names() %>%
  rename(
    wb_lifeExpecYrs          = life_expec,
    wb_mortalityInfant1k     = mortality_infant_1k,
    wb_mortalityMaternal100k = mortality_maternal_100k,
    wb_urbanPopPercent       = urban_pop_per
  ) %>%
  gencc %>%
  select(-wbcode, -cname) %>%
  mutate(pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, starts_with("wb_"))

## -------------- ##
## WB2 ----
wdi2 <- wdi2 %>%
  janitor::clean_names() %>%
  gencc %>%
  select(-wbcode, -cname, -cell_subs_p100) %>%
  rename(wb_internetPercent   = internet_per_pop,
         wb_cellSubscriptions = cell_subs_ct) %>%
  mutate(pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, starts_with("wb_"))


## -------------- ##
## IHME ----
## IHME health spending
## - Variable definitions:
##   - `the_total_mean` \~ Total Health Spending (thousands 2020 USD)
##   - `ghes_total_mean` \~ Government Health Spending (thousands 2020 USD)
##   - `oop_total_mean` \~ Out-of-pocket Health Spending (thousands 2020 USD)
##   - `dah_total_mean` \~ Development Assistance for Health (thousands 2020 USD)
##   - `the_per_cap_mean` \~ Total Health Spending per person (2020 USD)
##   - `ghes_per_cap_mean` \~ Government Health Spending per person (2020 USD)
##   - `oop_per_cap_mean` \~ Out-of-pocket Health Spending per person (2020 USD)
##   - `ghes_per_the_mean` \~ Government Health Spending per Total Health Spending (%)
ihme <- ihme %>%
  filter(level == "Country") %>%
  rename(cname = location_name) %>%
  mutate(cname = stringi::stri_trans_general(cname, "latin-ascii")) %>%
  gencc %>%
  mutate(ihme_totHealthUsd     = the_total_mean    * 1e3,
         ihme_govHealthUsd     = ghes_total_mean   * 1e3,
         ihme_oopHealthUsd     = oop_total_mean    * 1e3,
         ihme_dahHealthUsd     = dah_total_mean    * 1e3,
         ihme_govHealthPercent = ghes_per_the_mean * 100,
         ihme_oopHealthPercent = oop_per_the_mean  * 100,
         pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, starts_with("ihme_"))

## -------------- ##
## CEPII ----
cep <- cep %>%
  filter(year   >= 1998,
         iso3_d == iso3_o) %>%
  rename(gatt = gatt_d, wto = wto_d, eu = eu_d) %>%
  select(iso3_o, year, gatt, wto, eu) %>%
  as_tibble

tmp <- tibble(iso3_o = unique(cep$iso3_o)) %>%
  mutate(ccode = countrycode(iso3_o, "iso3c", "cown",
                             custom_match = c("SRB" = 345, "YUG" = 345)))

cep <- left_join(cep, tmp, by = "iso3_o") %>%
  drop_na(ccode) %>%
  mutate(pnid = paste(ccode, year, sep = "."),
         across(.cols = c(eu, gatt, wto),
                .fns  = ~replace_na(.x, 0))) %>%
  rename_with(.cols = c(eu, gatt, wto),
              .fn   = ~paste0("cepii_", .x)) %>%
  select(pnid, starts_with("cepii_")) %>%

  # Fix Serbia
  group_by(pnid) %>%
  summarize(across(.cols = everything(),
                   .fns  = max)) %>%
  ungroup

rm(tmp)

## ----------------------- ##
## UN - migration ----
# drop UN's data headers
migr <- migr %>%
  select(1:14) %>%
  slice(9:nrow(.))

# assign row 1 in data to column names
colnames(migr) <- migr[1,]

# subset and select relevant variables
migr <- migr %>%
  slice(2:nrow(.)) %>%
  rename(destination = 2, origin = 6) %>%
  select(origin, destination,
         `1995`, `2000`, `2005`, `2010`, `2015`, `2020`) %>%
  mutate(across(.cols = c(origin, destination),
                .fns  = ~str_remove(.x, "[*]"))) %>%
  # countrycode absolutely will code the following to china so  drop here
  filter(origin      != "Less developed regions, excluding China",
         destination != "Less developed regions, excluding China")

# assign country codes
tmp <- tibble(x = unique(c(migr$origin, migr$destination))) %>%
  mutate(ccode = countrycode(x, "country.name", "cown",
                             custom_match = c("Serbia" = 345)))

migr <- migr %>%
  left_join(., tmp, by = c("origin" = "x")) %>%
  rename(ccode_o = ccode) %>%
  left_join(., tmp, by = c("destination" = "x")) %>%
  rename(ccode_d = ccode) %>%
  drop_na(ccode_o, ccode_d) %>%
  select(ccode_o, ccode_d, everything(), -origin, -destination)

rm(tmp)

# pivot longer and interpolate
migr <- migr %>%
  pivot_longer(data            = .,
               cols            = !c(ccode_o, ccode_d),
               names_to        = "year",
               names_transform = as.numeric,
               values_to       = "stock") %>%
  arrange(ccode_o, ccode_d, year)


# expand missing years (and drop own country years, destination == origin)
migr <- migr %>%
  complete(ccode_d, ccode_o, year = full_seq(.$year, period = 1)) %>%
  filter(!(ccode_d == ccode_o))

# interpolate missing years (first drop dyads with 1 or no obs.)
migr <- migr %>%
  group_by(ccode_o, ccode_d) %>%

  filter(sum(!is.na(stock)) > 1) %>%

  mutate(stock = na_interpolation(x = stock, option = "linear")) %>%
  mutate(flow  = stock - lag(stock, n = 1)) %>%
  ungroup %>%
  filter(year >= 1999)

# summarize migrant stocks
# arrivals (destinations)
net_d <- migr %>%
  group_by(ccode_d, year) %>%
  summarize(un_migrantArrivals = sum(stock), .groups = "keep") %>%
  rename(ccode = ccode_d) %>%
  ungroup

# departures (origins)
net_o <- migr %>%
  group_by(ccode_o, year) %>%
  summarize(un_migrantDepartures = sum(stock), .groups = "keep") %>%
  rename(ccode = ccode_o) %>%
  ungroup

# copy migr to save for spatial weights
migr_w <- migr

# combine net migration summaries to test as covariats
migr <- full_join(net_d, net_o, by = c("ccode", "year")) %>%
  drop_na() %>%  # Vatican City only
  mutate(pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, starts_with("un_"))

rm(net_d, net_o)


# ------------------------------------- #
# 3 - merge ----
res <- list(pnl, cep, ihme, migr, ungdp, unpop, wdi1, wdi2) %>%
  purrr::reduce(left_join, by = "pnid")

# clean up
rm(pnl, cep, ihme, migr, ungdp, unpop, wdi1, wdi2, gencc)


# ------------------------------------- #
# 4 - save ----

# save controls
write_rds(x = res, file = here("10-data/02-tidy/03-controls.rds"))

# save migration dyads for spatial weights
write_rds(x = migr_w, file = here("10-data/02-tidy/03-migration.rds"))

rm(list = ls())
