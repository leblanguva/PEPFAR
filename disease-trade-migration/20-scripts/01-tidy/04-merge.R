# ------------------------------------- #
# name   : 01-tidy/04-merge
# purpose: this script joins all outcome and control variables for
#          disease-trade analysis
#
# imports:
#   - `10-data/02-tidy/01-disease.rds`
#     - tidied ihme disease data with pnid panel identifier for merging
#       Exported from `20-scripts/01-tidy/01-disease.R`
#   - `10-data/02-tidy/02-healthaid.rds`
#     - tidied pepfar and oecd health aid data with pnid panel identifier
#       Exported from `20-scripts/01-tidy/02-healthaid/default.R`
#   - `10-data/02-tidy/03-controls.rds`
#     - tidy panel of control variables
#       Exported from `20-scripts/01-tidy/03-controls.R`
#   - `10-data/02-tidy/00-panel.rds`
#     - tidy panel of countries with spatial geometry
#       Exported from `20-scripts/01-tidy/00-panel/default.R`
#
# exports:
#   - `10-data/02-tidy/04-merge.rds`
#      - full join of all tidied variables including observations with missing
#        values
#
# sections:
#     0 - setup
#     1 - merge
#     2 - per capita measures
#     3 - sort and arrange
#     4 - save



# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(sf)

library(here)
i_am("20-scripts/01-tidy/04-merge.R")

# load data
dis <- read_rds(here("10-data/02-tidy/01-disease.rds"))
hlt <- read_rds(here("10-data/02-tidy/02-healthaid.rds"))
ctr <- read_rds(here("10-data/02-tidy/03-controls.rds"))
pnl <- read_rds(here("10-data/02-tidy/00-panel.rds")) %>%
  st_drop_geometry %>% as_tibble


# ------------------------------------- #
# 1 - merge ----
# create sorted names for tidy
# (disease names, health names, control names, panel identifier names)
disn <- names(dis)[!str_detect(names(dis), "pnid")] %>%
  c(., paste0(., "100k")) %>% sort
hltn <- names(hlt)[!str_detect(names(hlt), "pnid")]             %>% sort
ctrn <- names(ctr)[!str_detect(names(ctr), c("pnid"))]          %>% sort
pnln <- names(pnl)[!str_detect(names(pnl), c("pnid|geometry"))] %>% sort

# merge data and create dv operationalizations (100k, lags, first-differences)
res <- list(pnl, dis, hlt, ctr) %>%
  purrr::reduce(., left_join, by = "pnid") %>%
  mutate(across(.cols = c(ihme_hiv, ihme_malaria, ihme_measles,
                          ihme_respinf, ihme_sti, ihme_tb),
                .fns  = list("100k" = ~(.x / un_popTotal) * 1e5),
                .names= "{.col}{.fn}")) %>%
  arrange(ccode, year) %>%
  group_by(ccode) %>%
  mutate(across(.cols = all_of(disn),
                .fns  = list("Lag" = ~lag(.x, n = 1),
                             "Fd"  = ~(.x - lag(.x, n = 1))),
                .names= "{.col}{.fn}")) %>%

  # Lag hiv100kFd - broken out since that is the main DV for now
  mutate(ihme_hiv100kFdLag = lag(ihme_hiv100kFd, n = 1)) %>%
  ungroup

rm(ctr,  dis,  hlt,  pnl)


# ------------------------------------- #
# 2 - per capita measures ----
# create new measures and update variable sort lists accordingly
# -   PEPFAR and OECD aid and GDP per capita
# -   UN GDP per capita
# -   UN Net migrants per capita (destination)
# -   President - presidential administration indicator
res <- res %>%
  mutate(
    across(.cols = c(pepfar, starts_with("oecd"), un_gdpUSD),
           .fns  = ~(.x / un_popTotal),
           .names= "{.col}Pc"),
    un_migrantNetPc = (un_migrantArrivals / un_popTotal) -
      (un_migrantDepartures / un_popTotal),
    president       = case_when(
      year %in% as.character(2001:2008) ~ "Bush",
      year %in% as.character(2009:2016) ~ "Obama",
      year %in% as.character(2017:2020) ~ "Trump",
      .default = NA_character_
    )
  ) %>%
  # Clinton years will always drop out
  mutate(president = factor(president,
                            levels = c("Bush", "Obama", "Trump")))


# ------------------------------------- #
# 3 - sort and arrange ----
# update variable list names
disn <- c(disn, paste0(disn, "Lag"), paste0(disn, "Fd"),
          "ihme_hiv100kFdLag") %>% sort
ctrn <- c(ctrn, "un_gdpUSDPc", "un_migrantNetPc", "president") %>% sort
hltn <- c(hltn, paste0(hltn, "Pc"))                            %>% sort

# select sorted variables
res <- res %>%
  select(pnid,
         all_of(pnln), all_of(disn), all_of(hltn), all_of(ctrn))

# cleanup
rm(ctrn, disn, hltn, pnln)

# convert id-variables to factors
res <- res %>%
  mutate(across(.cols = c(ccode, cname, region, region23, year),
                .fns  = as_factor))


# ------------------------------------- #
# 4 - save ----
write_rds(res, file = here("10-data/02-tidy/04-merge.rds"))

# save a csv format for ease of use elsewhere
write_csv(res, file = here("10-data/02-tidy/04-merge.csv"))

rm(list = ls())
