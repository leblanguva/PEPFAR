# ------------------------------------- #
# name   : 01-tidy/05-weights
# purpose: this script constructs spatial w data based on:
#          - distance (inverse) (source: computed here)
#          - trade              (source: CEPII)
#          - migration          (source: UN)
#
# imports:
#   - `10-data/02-tidy/03-controls.rds`
#     - tidy panel of control variables
#       Exported from `20-scripts/01-tidy/03-controls.R`
#   - `10-data/01-source/cepii_gravity/gravity_v202102.Rds`
#     - CEPII data
#   - `10-data/02-tidy/00-panel.rds`
#     - tidy panel of countries with spatial geometry
#       Exported from `20-scripts/01-tidy/00-panel/default.R`
##
# exports:
#   - ``
#      - x
#
# sections:
#     0 - setup
#     1 - shared
#     2 - non-spatial tidy
#     3 - non-spatial weights
#     4 - spatial weights
#     5 - weights cleanup
#     6 - save


# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(sf)
library(countrycode)

library(here)
i_am("20-scripts/01-tidy/05-weights/default.R")

# load data
un  <- read_rds(here("10-data/02-tidy/03-migration.rds"))
tr  <- read_rds(here("10-data/01-source/cepii_gravity/gravity_v202102.Rds"))
pnl <- read_rds(here("10-data/02-tidy/00-panel.rds"))

# load functions
sapply(list.files(here("20-scripts/01-tidy/05-weights"),
                  pattern    = "fn-",
                  full.names = T),
       source)

# local functions
trade_flow <- function(x, zero_na = FALSE){
  # computes trade flow as average of comtrade and imf sources and handles NAs
  # These zero cases are handled with filter logic below
  if(all(is.na(x)) & zero_na){
    return(0)
  } else{
    return(mean(x, na.rm = TRUE))
  }
}


# ------------------------------------- #
# 1 - shared ----
# years over which to construct matrices
w_years <- 2000:2019

# names for each matrix
w_names <- paste("year", w_years, sep = ".")


# ------------------------------------- #
# 2 - non-spatial tidy ----
## migration
un <- un %>%
  filter(year >= min(w_years) & year <= max(w_years)) %>%
  mutate(pnid_o = paste(ccode_o, year, sep = "."),
         pnid_d = paste(ccode_d, year, sep = ".")) %>%
  filter(pnid_o %in% pnl$pnid,
         pnid_d %in% pnl$pnid) %>%
  as_tibble

## trade
# correct Serbia
tr <- tr %>%
  filter(
    !(iso3_o == "SRB" & year %in% 2000:2005),
    !(iso3_d == "SRB" & year %in% 2000:2005),
    !(iso3_o == "YUG" & year %in% 2006:2019),
    !(iso3_d == "YUG" & year %in% 2006:2019),
  )

# generate ccodes
tr <- tr %>%
  filter(year >= min(w_years)) %>%
  gencc(src = "iso3_o") %>% rename(ccode_o = ccode) %>%
  gencc(src = "iso3_d") %>% rename(ccode_d = ccode) %>%
  mutate(pnid_o = paste(ccode_o, year, sep = "."),
         pnid_d = paste(ccode_d, year, sep = ".")) %>%
  filter(pnid_o %in% pnl$pnid,
         pnid_d %in% pnl$pnid)

# unify tradeflow average (imf, comtrade)
tr <- tr %>%
  mutate(across(.cols = starts_with("tradeflow"),
                .fns  = ~.x * 1e3)) %>%
  mutate(flow = apply(.[,c("tradeflow_comtrade_d",
                           "tradeflow_imf_d")], 1, trade_flow,
                      zero_na = TRUE)) %>%

  # Drop cases with zero reported trade - island cases reflect missing data
  group_by(ccode_d, year) %>%
  mutate(tst = sum(flow)) %>%
  ungroup

# identify cases with no reported trade - need to drop origin cases for balance
drops <- tr %>% filter(tst == 0) %>% pull(pnid_d) %>% unique

tr <- tr %>%
  filter(!pnid_d %in% drops,
         !pnid_o %in% drops) %>%
  select(ccode_d, ccode_o, year, pnid_o, pnid_d, flow) %>%
  as_tibble

rm(trade_flow, drops, gencc)


# ------------------------------------- #
# 3 - non-spatial weights ----
wNonSpatial <- list(
  "trade"     = lapply(w_years, w_dyad, data = tr, name_variable = "flow"),
  "migration" = lapply(w_years, w_dyad, data = un, name_variable = "stock")
)

names(wNonSpatial$trade)     <- w_names
names(wNonSpatial$migration) <- w_names

# cleanup
rm(tr, un, w_dyad)


# ------------------------------------- #
# 4 - spatial weights ----
# define projection
# oblique azimuthal equidistant projection for accurate global distances
prj_string <- "+proj=aeqd +lon_0=0 +lat_0=0 +datum=WGS84 +units=km +no_defs"

# project spatial dataframe
pnl <- pnl %>%
  select(pnid, year) %>%
  st_transform(., st_crs(prj_string)) %>%
  st_centroid

rm(prj_string)

# compute distance based weights
wDistance        <- lapply(w_years, w_dist, data = pnl)
names(wDistance) <- w_names

# cleanup
rm(w_dist, w_inv, pnl)


# ------------------------------------- #
# 5 - weights cleanup ----
## combine non-spatial and spatial weight matrices into a single list
weights <- c(wNonSpatial, list("distance" = wDistance))

# cleanup
rm(wDistance, wNonSpatial)

# subset all weight variants (distance, trade, migration) to have identical
# observations within each analysis year.
weights        <- lapply(w_names, w_unique, wlist = weights, tidy_w = TRUE)
names(weights) <- w_names


# ------------------------------------- #
# 6 - save ----
save(weights, file = here("10-data/02-tidy/05-weights.rdata"))
rm(list = ls())

