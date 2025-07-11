# ------------------------------------- #
# name   : 02-analysis/03-fit
# purpose: fits Bayesian non-spatial and spatial models
#
# imports :
#   - `10-data/03-analysis/00-stan-models.rds`
#     - compiled stan models.
#       Exported from `20-scripts/02-analysis/00-stan-models/default.R`
#   - `10-data/03-analysis/01-analysis-weights.rdata`
#     - trade, distance, and migration spatial weights with only observations
#       corresponding to rows in data with no missing values on covariates.
#       Exported from `20-scripts/02-analysis/01-data.R`
#   - `10-data/03-analysis/01-analysis-data.rdata`
#     - data containing rows with no missing values for covariates
#       Exported from `20-scripts/02-analysis/01-data.R`
#
# exports:
#   - `10-data/03-analysis/03-fit-main.rdata`
#     - main regression models
#   - `10-data/03-analysis/03-fit-appendix.rdata`
#     - appendix regression models
#
# sections:
#   0 - setup
#   1 - fit models -- main. Bayesian non-spatial and spatial models with 1, 2,
#       and 3 simultaneous spatial weights matrices
#   2 - fit models -- appendix. distance and migration auxiliary Bayes models
#       and mle models fit with spatialreg::lagsarlm
#   3 - save results


# ------------------------------------- #
# 0 - setup ----
# Clear environment
rm(list = ls())

# Load packages
library(tidyverse)
library(rstan)
library(spdep)
library(spatialreg)

library(here)
i_am("20-scripts/02-analysis/03-fit/default.R")

# Load data
bm <- read_rds(here("10-data/03-analysis/00-stan-models.rds")) # bm ~ bayes model
load(here("10-data/03-analysis/01-analysis-weights.rdata"))
load(here("10-data/03-analysis/01-analysis-data.rdata"))

# Load functions
source(here("20-scripts/02-analysis/03-fit/fn-fit.R"))


# ------------------------------------- #
# 1 - fit models -- main ----
# non-spatial
m1 <- fit(formula = d$form$base,     data = d$data, model = bm$non_spatial)
m2 <- fit(formula = d$form$controls, data = d$data, model = bm$non_spatial)

# spatial
m3 <- fit(formula = d$form$controls,
          data    = d$data,
          model   = bm$spatial_w1,
          weights = list("W1"     = spatial$weights$trade),
          evals   = list("evals1" = spatial$eigenvalues$trade))
m4 <- fit(formula = d$form$controls,
          data    = d$data,
          model   = bm$spatial_w2,
          weights = list("W1" = spatial$weights$trade,
                         "W2" = spatial$weights$distance),
          evals   = list("evals1" = spatial$eigenvalues$trade,
                         "evals2" = spatial$eigenvalues$distance))
m5 <- fit(formula = d$form$controls,
          data    = d$data,
          model   = bm$spatial_w3,
          weights = list("W1" = spatial$weights$trade,
                         "W2" = spatial$weights$distance,
                         "W3" = spatial$weights$migration),
          evals   = list("evals1" = spatial$eigenvalues$trade,
                         "evals2" = spatial$eigenvalues$distance,
                         "evals3" = spatial$eigenvalues$migration))

# collect main models into organized list and clean up
res_main <- lst("m1_nonspatial_base"                    = m1,
                "m2_nonspatial_controls"                = m2,
                "m3_spatialW1_trade"                    = m3,
                "m4_spatialW2_trade_distance"           = m4,
                "m5_spatialW3_trade_distance_migration" = m5)
rm(m1,m2,m3,m4,m5)
gc()


# ------------------------------------- #
# 2 - fit models -- appendix ----
# distance and migration auxiliary Bayes models and mle models fit with
# spatialreg::lagsarlm

# a1 - distance only
a_1 <- fit(formula = d$form$controls,
           data    = d$data,
           model   = bm$spatial_w1,
           weights = list("W1"     = spatial$weights$distance),
           evals   = list("evals1" = spatial$eigenvalues$distance))

# a2 - migration only
a_2 <- fit(formula = d$form$controls,
           data    = d$data,
           model   = bm$spatial_w1,
           weights = list("W1"     = spatial$weights$migration),
           evals   = list("evals1" = spatial$eigenvalues$migration))

# a3 - distance and migration
a_3 <- fit(formula = d$form$controls,
           data    = d$data,
           model   = bm$spatial_w2,
           weights = list("W1"     = spatial$weights$distance,
                          "W2"     = spatial$weights$migration),
           evals   = list("evals1" = spatial$eigenvalues$distance,
                          "evals2" = spatial$eigenvalues$migration))

# a4 - trade and migration
a_4 <- fit(formula = d$form$controls,
           data    = d$data,
           model   = bm$spatial_w2,
           weights = list("W1"     = spatial$weights$trade,
                          "W2"     = spatial$weights$migration),
           evals   = list("evals1" = spatial$eigenvalues$trade,
                          "evals2" = spatial$eigenvalues$migration))

# appendix mle
# note -- all mle models only use a single-W spatial weights matrix

a_mle <- sapply(names(spatial$weights), function(w){
  lagsarlm(formula = d$form$controls,
           data    = d$data,
           method  = "eigen",
           listw   = spatial$list_ws[[w]],
           control = list(pre_eig = spatial$eigenvalues[[w]]))
}, simplify = F, USE.NAMES = T)

# collect appendix models into organized list and clean up
res_appendix <- lst("a1_spatialW1_distance"           = a_1,
                    "a2_spatialW1_migration"          = a_2,
                    "a3_spatialW2_distance_migration" = a_3,
                    "a4_spatialW2_trade_migration"    = a_4,
                    "aa_spatialW1_mle"                = a_mle)
rm(a_1, a_2, a_3, a_4, a_mle)
gc()


# ------------------------------------- #
# 3 - save ----
save(res_main,     file = here("10-data/03-analysis/03-fit-main.rdata"))
save(res_appendix, file = here("10-data/03-analysis/03-fit-appendix.rdata"))

rm(list = ls())
