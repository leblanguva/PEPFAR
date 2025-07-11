# ------------------------------------- #
# name   : 02-analysis/00-stan-models
# purpose: this script constructs, compiles, and exports R `stan` model objects
# - Regarding priors, see
#     (https://github.com/stan-dev/stan/wiki/Prior-Choice-Recommendations)
# - All models employ a QR reparameterization of the design matrix X.
#   - For more on QR reparamererization, see
#     (https://mc-stan.org/docs/stan-users-guide/QR-reparameterization.html)
#   - This improves orthagonality of variables easing search costs of
#     parameter space. It further places variables on an equivalent
#     scale allowing for a weakly informative prior ~Normal(0, 1)
#
# imports:
#   - `./*.stan`
#     - non-spatial and spatial regression models declared in stan language
#       imported from the same sub-directory as this script
#
# exports:
#   - `10-data/03-analysis/00-stan-models.rds`
#      - compiled stan model objects ready for model fitting via rstan::sampling
#
# sections:
#     0 - setup
#     1 - compile models
#     2 - save


# ------------------------------------- #
# 0 - setup ----

# Clear environment
rm(list = ls())

# Load packages
library(readr)
library(rstan)
library(stringr)

library(here)
i_am("20-scripts/02-analysis/00-stan-models/default.R")


# ------------------------------------- #
# 1 - compile models ----
# note - can ignore xcode warnings
mods <- list.files(path       = here("20-scripts/02-analysis/00-stan-models"),
                   full.names = TRUE,
                   pattern    = ".stan")

mods_compiled <- lapply(mods, function(x){
  return(stan_model(file       = x,
                    model_name = str_remove(basename(x), ".stan")))
})

names(mods_compiled) <- str_remove(basename(mods), ".stan")


# ------------------------------------- #
# 2 - save ----
write_rds(x    = mods_compiled,
          file = here("10-data/03-analysis/00-stan-models.rds"))

rm(list = ls())
