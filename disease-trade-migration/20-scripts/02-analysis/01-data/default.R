# ------------------------------------- #
# name   : 02-analysis/01-data
# purpose: subsets data to observations and variables used in empirical models
#
#          Using this subset, this script also computes spatial weight marginals
#          and composition of country-year trade with PEPFAR recipients
#
#          This script also computes for each country-year the percentage of
#          country_i's trade with PEPFAR recipients. These values - stored as a
#          variable in the data output from this script - are used to identify
#          cases for meaningful marginal effects.
#
# imports:
#   - `10-data/02-tidy/05-weights.rdata`
#     - full spatial weights matrices (broken apart by year) with all
#       observations (including country years with missing covariate data)
#       Exported from `20-scripts/01-tidy/05-weights.R`
#   - `10-data/02-tidy/04-merge.rds`
#     - full data with all covariates and observations including rows with
#       missing data
#       Exported from `20-scripts/01-tidy/04-merge.R`
#
# exports:
#   - `10-data/03-analysis/01-analysis-data.rdata`
#     - data only containing rows with no missing data for covariates
#   - `10-data/03-analysis/01-analysis-weights.rdata`
#     - row-standardized spatial weights containing only cases represented in
#       data with no missing covariate measures
#
# sections:
#     0 - setup
#     1 - compute % of country i's total trade with PEPFAR recipients
#     2 - collect yearly spatial weights into a large nT x nT block-diagonal
#         matrix
#     3 - tidy analysis data by dropping variables not used in models and
#         rows with missing observations.
#     4 - subset spatial weight matrices using cases in tidied data from (3)
#     5 - collect objects into lists for tidy export and save


# ------------------------------------- #
# 0 - setup ----

# Clear environment
rm(list = ls())

# Load packages
library(tidyverse)
library(sf)
library(countrycode)
library(magic)
library(spdep)

library(here)
i_am("20-scripts/02-analysis/01-data/default.R")

# load data
load(here("10-data/02-tidy/05-weights.rdata"))
d <- read_rds(here("10-data/02-tidy/04-merge.rds"))

# load functions
sapply(list.files(here("20-scripts/02-analysis/01-data"),
                  pattern    = "fn-",
                  full.names = TRUE),
       source)


# ------------------------------------- #
# 1 - compute trade with PEPFAR recipients ----
# subset trade spatial weights
wTrade <- weights %>% purrr::map(., "trade")
wTrade <- wTrade[!str_detect(names(wTrade), paste(2000:2003, collapse = "|"))]
names(wTrade) <- str_remove_all(names(wTrade), "year.")

# Extract country-codes of annual PEPFAR recipients
pepfarCountries <- d %>%
  filter(pepfar > 0) %>%
  select(pnid) %>%
  separate_wider_delim(pnid,
                       names = c("ccode", "year"),
                       delim = ".")

# Compute PEPFAR vs Non-PEPFAR trade among all Non-PEPFAR countries by
# iterating over the names (`year`) of `wTrade`.
# Compute percent of country-i trade with PEPFAR recipient countries
res <- lapply(names(wTrade), function(wyr, verbose = T){
  if(verbose){cat(sprintf("\14Working on year: %s", wyr))}

  # Extract wTrade year subset
  w <- wTrade[[wyr]]

  # Identify PEPFAR recipients in that year
  pepfarYr <- pepfarCountries %>% filter(year == as.numeric(wyr)) %>%
    pull(ccode) %>%
    as.character

  pepfarRecip <- paste(pepfarYr, wyr, sep = ".")

  # Apply the calcTrade function to each row in W
  out <- lapply(rownames(w),
                function(x){calcTrade(rn = x,
                                      w  = w,
                                      pepfarRecipients = pepfarYr)}) %>%
    bind_rows %>%
    mutate(pepfarCat = case_when(pnid %in% pepfarRecip ~ "PEPFAR - Yes",
                                 .default              = "PEPFAR - No"))

  return(out)
}) %>%
  bind_rows %>%
  select(-year) %>%
  rename_with(.cols = !pnid,
              .fn   = ~paste0("analysis_", .x))

# Join PEPFAR trade percentages back to main dataset using `pnid`
d <- left_join(d, res, by = "pnid")

# clean up
rm(res, calcTrade, wTrade, pepfarCountries)


# ------------------------------------- #
# 2 - collect yearly spatial weights ----
weights_full <- list("weights"   = weights,
                     "functions" = list("sub"    = wsub,
                                        "rowstd" = wrs))

# Full panel weights
wTrade     <- do.call(adiag, weights %>% purrr::map(., "trade"))
wMigration <- do.call(adiag, weights %>% purrr::map(., "migration"))
wDistance  <- do.call(adiag, weights %>% purrr::map(., "distance"))

weights <- list("trade"     = wTrade,
                "migration" = wMigration,
                "distance"  = wDistance)

rm(wTrade, wMigration, wDistance)


# ------------------------------------- #
# 3 - tidy analysis data ----
d <- d %>%
  arrange(as.numeric(ccode), as.numeric(year)) %>%
  mutate(
    un_popDensSqkm         = log(un_popDensSqkm),
    un_gdpUSDPc            = log(un_gdpUSDPc),
    un_e2i                 = un_exportsUSD / un_importsUSD,
    ihme_gov2oop           = ihme_govHealthUsd / ihme_oopHealthUsd,
    wb_mortalityInfant100k = log(wb_mortalityInfant1k * 100),
    analysis_tradePepfarPercent2 = analysis_tradePepfarPercent^2
  ) %>%

  # compute first differences for control variables
  group_by(ccode) %>%
  mutate(across(.cols  = c(oecd_disStdhivAid2020usdPc,
                           oecd_basicAid2020usdPc,
                           oecd_reproductiveAid2020usdPc,
                           oecd_disInfectiousAid2020usdPc,

                           un_popDensSqkm, un_gdpUSDPc, un_migrantNetPc,
                           un_importsUSD, un_exportsUSD, un_e2i,

                           wb_internetPercent, wb_lifeExpecYrs,
                           wb_mortalityInfant100k,

                           ihme_govHealthUsd, ihme_oopHealthUsd,
                           ihme_gov2oop
  ),
  .fns   = ~.x - lag(.x, n = 1),
  .names = "{.col}")) %>%
  ungroup %>%
  select(-wb_mortalityInfant1k) %>%

  # drop observations in data with no values in trade spatial weights matrix
  prepData(., w = weights$trade) %>%
  arrange(as.numeric(year), as.numeric(ccode))

rm(prepData)

# Note - prepData has now dropped cases not present in spatial weights, such
# as islands with no neighbors.
# An additional drop step will occur next dropping observations with missing
# values on control variables. These dropped observations will also subsequently
# be removed from all three spatial weights matrices.

fs <- lst(
  base = formula(ihme_hiv100kFd ~ ihme_hiv100kFdLag +
                 pepfarPc * analysis_tradePepfarPercent *
                 analysis_tradePepfarPercent2 -

                 # this constituent term introduces additional multicollinarity
                 # and is irrelevant to computing pepfarPc marginal effects,
                 # so excluding here
                 analysis_tradePepfarPercent:analysis_tradePepfarPercent2),

  controls = update(base, . ~ . +
                oecd_disStdhivAid2020usdPc +
                oecd_basicAid2020usdPc +
                oecd_reproductiveAid2020usdPc +
                oecd_disInfectiousAid2020usdPc +
                ihme_gov2oop +

                un_popDensSqkm + un_gdpUSDPc + un_e2i +
                wb_internetPercent + wb_lifeExpecYrs + wb_mortalityInfant100k)
)

# Create model frame (columns and rows in data with no NA based on
# formula: `controls` specified above)
dd <- model.frame(fs$controls, d, drop.unused.levels = TRUE) %>% tibble

# extract panel-ids (pnid) NOT dropped due to NAs
id <- d$pnid[!rownames(d) %in% na.action(dd)]

# subset analysis data to only retain cases with observations for all variables
d  <- d %>% filter(pnid %in% id) %>%
  mutate(across(.cols = where(is.factor),
                .fns  = fct_drop))


# add country and year fixed effects to formulas
fs <- lapply(fs, update, . ~ . -1 + cname + year)

# clean up
rm(dd, id)


# ------------------------------------- #
# 4 - subset spatial weight matrices ----
# subset weights -- retain only cases in data designated with panel id (pnid)
weights <- lapply(weights, wsub, ids = d$pnid, rs = FALSE)

# Note - dims of spatial weights matrix (row x column) now = rows in data
# dim(weights$trade)[1] == nrow(d)

# compute trade and migration totals from weights for bivariate mapping
# note - weight values still presently raw numbers (trade total USD and
#        total migration in persons) so row sums represent annual sums
d$analysis_wTrade     <- rowSums(weights$trade)
d$analysis_wMigration <- rowSums(weights$migration)

# row-standardize weights
weights <- lapply(weights, wrs)

# compute spatial weight eigenvalues for spatial modeling and effect calculations
eigenvalues <- lapply(weights, eigen, only.value = TRUE) %>%
  purrr::map(., "values") %>%
  lapply(., as.numeric)

# construct list-w object for comparison single-W mle fits using spatialreg::lagsarlm
lws <- lapply(weights, mat2listw, style = "W")

# clean up
rm(wsub, wrs)


# ------------------------------------- #
# 5 - save ----
# a list of variable names in data and corresponding names to use in all
# tables and figures for consistency
vnames <- c(
  "pepfarPc"                             = "PEPFAR Aid",

  "analysis_tradePepfarPercent"          = "PEPFAR Trade",
  "analysis_tradePepfarPercent2"         = "PEPFAR Trade$^{2}$",

  "pepfarPc:analysis_tradePepfarPercent" ="PEPFAR Aid $\\times$ PEPFAR Trade",
  "pepfarPc:analysis_tradePepfarPercent2"="PEPFAR Aid $\\times$ PEPFAR Trade$^{2}$",


  "pepfarPc:analysis_tradePepfarPercent:analysis_tradePepfarPercent2" = "PEPFAR Aid $\\times$ PEPFAR Trade $\\times$ PEPFAR Trade$^{2}$",


  "oecd_disStdhivAid2020usdPc"     = "OECD STI aid",
  "oecd_basicAid2020usdPc"         = "OECD General health aid",
  "oecd_reproductiveAid2020usdPc"  = "OECD Reproductive health aid",
  "oecd_disInfectiousAid2020usdPc" = "OECD Infectious disease aid",
  "ihme_gov2oop"                   = "Public/Private health spending ratio",
  "un_popDensSqkm"                 = "Pop. density$^{\\circ}$",
  "un_gdpUSDPc"                    = "GDP PC$^{\\circ}$",
  "un_e2i"                         = "Export/Import ratio",
  "wb_internetPercent"             = "Internet access",
  "wb_lifeExpecYrs"                = "Life expecectancy",
  "wb_mortalityInfant100k"         = "Infant mortality$^{\\circ}$",

  "ihme_hiv100kFd"              = "HIV incidence rate (per 100k)",
  "ihme_hiv100kFdLag"              = "HIV incidence rate (per 100k, lag)",

  "(Intercept)"                    = "Intercept",
  # For main regression result models
  "rho1"                           = "Rho - Trade",
  "rho2"                           = "Rho - Distance",
  "rho3"                           = "Rho - Migration",

  # For appendix Bayes regression result models
  "rho.trade"                      = "Rho - Trade",
  "rho.distance"                   = "Rho - Distance",
  "rho.migration"                  = "Rho - Migration",

  # For appendix MLE regression result models
  "rho"                            = "Rho"
)

# spatial elements
spatial <- lst("weights"      = weights,
               "eigenvalues"  = eigenvalues,
               "weights_full" = weights_full,
               "list_ws"      = lws)

rm(weights, eigenvalues, weights_full, lws)

# data elements
d <- lst("data" = d, "form" = fs, vnames);rm(fs,vnames)

# save
save(spatial, file = here("10-data/03-analysis/01-analysis-weights.rdata"))
save(d,       file = here("10-data/03-analysis/01-analysis-data.rdata"))

# save a csv format for ease of use elsewhere
write_csv(d$data, file = here("10-data/03-analysis/01-analysis-data.csv"))

rm(list = ls())

