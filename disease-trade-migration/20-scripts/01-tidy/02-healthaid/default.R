# ------------------------------------- #
# name   : 01-tidy/02-healthaid
# purpose: this script tidies health aid data from PEPFAR and OECD
#
# notes:
#   - due to large file sizes, OECD CRS data sets are stored in compressed zip
#     files (~680MB zipped vs ~6.2GB uncompressed) and imported and decompressed
#     using a helper function `tidy_oecd_crs` imported from this scripts dir.
#
# imports:
#   - `10-data/01-source/pepfar/PEPFAR_OU_Budgets_by_Financial_Classifications.txt`
#     - PEPFAR financial expenditure data
#   - `10-data/01-source/oecd/crs-zip/crs_*.zip`
#     - compressed OECD aid data disaggregated by year
#   - `10-data/02-tidy/00-panel.rds`
#     - tidy panel of countries with spatial geometry
#       Exported from `20-scripts/01-tidy/00-panel/default.R`
#
# exports:
#   - `10-data/02-tidy/02-healthaid.rds`
#      - tidied pepfar and oecd health aid data with pnid panel identifier
#        for merging
#
# sections:
#     0 - setup
#     1 - tidy panel
#     2 - tidy pepfar
#     3 - tidy oecd
#     4 - merge
#     5 - save


# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(lubridate)
library(sf)

library(here)
i_am("20-scripts/01-tidy/02-healthaid/default.R")

# load data
pepfar <- read_delim(
  file = here(
    "10-data/01-source/pepfar/PEPFAR_OU_Budgets_by_Financial_Classifications.txt"
    ),
  delim     = "\t",
  col_names = TRUE,
  progress  = FALSE,
  show_col_types = FALSE)

pnl  <- read_rds(here("10-data/02-tidy/00-panel.rds"))

# load functions
source("20-scripts/01-tidy/fn-gencc.R")
source("20-scripts/01-tidy/02-healthaid/fn-tidy_oecd_crs.R")

# ------------------------------------- #
# 1 - tidy panel ----
# retain only id to avoid variable duplication
pnl <- pnl %>%
  st_drop_geometry %>%
  as_tibble %>%
  select(pnid)


# ------------------------------------- #
# 2 - tidy pepfar ----
# note: warning on countrycode safe to ignore
pepfar <- pepfar %>%
  janitor::clean_names() %>%
  rename(cname = country_operating_unit) %>%
  filter(cname   != "Total",
         program == "Total") %>%
  gencc %>%
  pivot_longer(data  = .,
               cols  = starts_with("x"),
               names_to     = "year",
               names_prefix = "x",
               values_to    = "pepfar") %>%
  filter(year %in% 2004:2019) %>%
  mutate(pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, pepfar) %>%
  drop_na(pepfar)


# ------------------------------------- #
# 3 - tidy oecd ----
# note: parsing warning issues can be safely ignored
oecd_zip_files <- list.files(here("10-data/01-source/oecd/crs-zip/"),
                             full.names = TRUE)

oecd <- lapply(oecd_zip_files, function(x){
  cat(sprintf("Working on: %s\n", x))
  tidy_oecd_crs(path = x)
}) %>% bind_rows

rm(tidy_oecd_crs)

# clean recipient country names and assign country codes
# note: warning on countrycode safe to ignore
Encoding(oecd$cname) <- "latin1"
oecd <- oecd %>%
  mutate(cname = stringi::stri_trans_general(cname, "latin-ascii")) %>%
  mutate(cname = case_when(
    cname %in% c("Turkiye", "TA 1/4rkiye") ~ "Turkey", .default = cname)) %>%
  gencc %>%
  select(ccode, year, oecd_class, aid2020usd)

# summarize total aid received and pivot wide (aid categories)
oecd <- oecd %>%
  group_by(ccode, year, oecd_class) %>%
  summarize(Aid2020usd = sum(aid2020usd), .groups = "keep") %>%
  ungroup %>%
  pivot_wider(data        = .,
              id_cols     = c(ccode, year),
              names_from  = oecd_class,
              names_glue  = "{oecd_class}{.value}",
              values_from = Aid2020usd) %>%
  mutate(across(.cols = !c(ccode, year),
                .fns  = ~replace_na(.x, 0)),
         pnid = paste(ccode, year, sep = ".")) %>%
  select(pnid, everything(), -ccode, -year)

# total health aid
oecd <- oecd %>%
  rowwise %>%
  mutate(totalAid2020usd = sum(c_across(cols = !pnid))) %>%
  ungroup

# variable id
oecd <- oecd %>%
  rename_with(.data  = .,
              .cols = !pnid,
              .fn   = ~paste0("oecd_", .x))


# ------------------------------------- #
# 4 - merge ----
# note: treating NA observations as $0 aid from PEPFAR or OECD. Assumes
#       underlying data sources are complete aid financial allocation records
res <- pnl %>%
  left_join(., pepfar, by = "pnid") %>%
  left_join(., oecd,   by = "pnid") %>%
  mutate(across(.cols = !c(pnid),
                .fns  = ~replace_na(.x, 0))) %>%
  mutate(year   = as.numeric(str_extract("540.2007", "[0-9]{4}")),
         pepfar = case_when(year < 2004 ~ NA_integer_,
                            .default = pepfar)) %>%
  select(-year)


# ------------------------------------- #
# 5 - save ----
write_rds(x = res, file = here("10-data/02-tidy/02-healthaid.rds"))
rm(list = ls())
