# ------------------------------------- #
# name   : 02-analysis/04-effects
# purpose: this script estimate dynamic effects from fit regression models

# -   Imports:
# -   `03_fit-main.rdata` - from `20-scripts/02-analysis/03_fit.qmd`
# -   `01_analysis-data.rdata` - from `20-scripts/02-analysis/01_analysis-data.qmd`
# -   `01_analysis-weights.rdata` - from `20-scripts/02-analysis/01_analysis-data.qmd`
# -   Exports:
#   -   `10-data/03-analysis/04_effects.rdata`

#
# imports:
#   - `10-data/03-analysis/03-fit-main.rdata`
#     - fit regression models
#       Exported from `20-scripts/02-analysis/03-fit.R`
#   - `10-data/03-analysis/01-analysis-data.rdata`
#     - tidied data containing only observations and variables used in models
#       Exported from `20-scripts/02-analysis/01-data.R`
#   - `10-data/03-analysis/01-analysis-weights.rdata`
#     - tidied spatial weights containing only observations contained in data
#       Exported from `20-scripts/02-analysis/01-data.R`
#
# exports:
#   - `10-data/03-analysis/04-effects.rdata`
#      - all marginal effect estimates from fit regression models computed in
#        this script
#
# sections:
#     0 - setup
#     1 - lrss setup
#     2 - lrss effects
#     3 - lrss predictions
#     4 - save


# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(rstan)
library(countrycode)
library(texreg)

library(here)
i_am("20-scripts/02-analysis/04-effects/default.R")

# load data
load(here("10-data/03-analysis/03-fit-main.rdata"))
load(here("10-data/03-analysis/01-analysis-data.rdata"))
load(here("10-data/03-analysis/01-analysis-weights.rdata"))

# load functions
source(here("20-scripts/02-analysis/04-effects/fn-lrss.R"))
source(here("20-scripts/02-analysis/04-effects/fn-effects.R"))


# ------------------------------------- #
# 1 - lrss setup ----
# LRSS spatial (trade) weights
# NOTE - LRSS represents the final post temporal equilibrium response in Y
# (HIV incidence per 100k) for each unit $i$ in the data. I use the spatial
# network from the final year of observed data to estimate LRSS results.
wt <- spatial$weights$trade
wt <- wt[str_ends(rownames(wt), "2018"), str_ends(colnames(wt), "2018")]
ev <- eigen(wt, only.values = TRUE)$values %>% as.numeric

# create a storage list for results
results <- lst()


# ------------------------------------- #
# 2 - lrss effects ----
# - This block computes LRSS marginal effects of PEPFAR dollars across a
#   representative range of PEPFAR-trade contexts. It returns two elements in
#   the `results` list:
#
#   - `lrss` - the LRSS marginal effect of an additional dollar of PEPFAR aid on
#     HIV incidence (per 100k) across a representative range of PEPFAR trade
#     values for both the Non-spatial and Spatial (W1-trade) models. This
#     `lrss` element is itself a list comprised of two sub-elements:
#     `dynamics` and `effects`.
#     - `dynamics` - contain estimates of the 90% life of effect for the
#       response curves and, for the spatial models, the percentage of variation
#       in the effect attributable to Direct and Indirect spatial responses.
#     - `effects` - contain marginal effect estimates across PEPFAR-trade values:
#       - The W1 trade model results include: direct, indirect, and total LRSS
#         estimates while the Non-spatial model results only include total LRSS
#         estimates.
#       - These results will be used to produce a conditional effects plot.
#
#   - `lrssTable` - the LRSS marginal effect of an additional dollar of PEPFAR
#     aid on HIV incidence (per 100k) at two PEPFAR trade values
#     (0.05, and 0.15) to construct a succinct marginal effects table.
#
# Other notes:
# -   PEPFAR-trade values range from 0 to 3rd quartile of observed values.
# -   0 is very close to the 1st quartile which is at 2.9% PEPFAR trade.
# -   The marginal effect of PEPFAR aid becomes insignificant around 11%
#    (non-spatial) or 12% (spatial) of trade with other PEPFAR countries.

zvals <- seq(0,
             quantile(d$data$analysis_tradePepfarPercent, probs = 0.75),
             by = 0.01)

results$lrss$dynamics <- lapply(zvals[1], function(x){
  ns <- lrss(obj = res_main$m2_nonspatial_controls, z = x) %>%
    mutate(model = "Non-spatial")

  w1 <- lrss(obj = res_main$m3_spatialW1_trade, z = x, evs = list("trade" = ev)) %>%
    mutate(model = "Spatial - W1 Trade")

  dynamics <- bind_rows(
    ns %>% filter(effect %in% c("life90")),
    w1 %>% filter(effect %in%
                    c("life90", "directPercent", "indirectPercent"))
  )

  return(dynamics)
}) %>% bind_rows()


results$lrss$effects <- lapply(zvals, function(x){
  ns <- lrss(obj = res_main$m2_nonspatial_controls, z = x) %>%
    mutate(model = "Non-spatial")

  w1 <- lrss(obj = res_main$m3_spatialW1_trade, z = x, evs = list("trade" = ev)) %>%
    mutate(model = "Spatial - W1 Trade")

  effects <- bind_rows(
    ns %>% filter(!effect %in% c("life90")),
    w1 %>% filter(!effect %in%
                    c("life90", "directPercent", "indirectPercent"))
  )

  return(effects)
}) %>% bind_rows()

rm(zvals)

lrss515 <- results$lrss$effects %>%
  filter(effect == "total", zAt %in% c(0.05, 0.15)) %>%
  mutate(zNames = paste("PEPFAR Trade -", sprintf("%s%%", zAt*100)))

# generate PEPFAR - long run steady state (lrss) effect estimates on HIV
# reductions at different levels of trade with PEPFAR recipients
results$lrssTable <- lapply(unique(lrss515$model), function(x){
  tmp <- lrss515 %>% filter(model == x)
  out <- createTexreg(
    coef.names = tmp$zNames,
    coef       = tmp$median,
    ci.low     = tmp$lower,
    ci.up      = tmp$upper,
    model.name = x
  )
  return(out)
})

rm(lrss515)


# ------------------------------------- #
# 3 - lrss predictions ----
# - This block computes predicted HIV case reductions in response to a
#   representative PEPFAR aid shock (median among PEPFAR recipients) for "ideal"
#   recipient countries.
#
#   First, ideal PEPFAR recipient countries are identified.
#   Second, long-run direct and indirect HIV reductions in response to the
#   PEPFAR aid shock are computed.
#
# - Ideal recipient country identification:
#   - Ideal recipient countries are identified as:
#       + those having HIV incidence rates (per 100k) that are two inter-quartile
#         range deviations above the median incidence rate in the observed data
#       + those who have never received PEPFAR aid
#       + those where average annual trade with PEPFAR recipient countries is
#         12% or less.
#   - These countries are stored in the `results` list as: `ideal`
#
# - HIV reduction calculations:
#
#   - Ideal country - trade partner specific HIV reductions:
#     - For each `ideal` recipient country total HIV reductions in response to
#       the PEPFAR shock are estimated using estimated LRSS marginal effects
#       computed using each `ideal` country's reported PEPFAR-trade value and
#       trade-partner country populations.
#         - Trade-partner populations are appropriately weighted by the spatial
#           (trade) weights. Where $country_{i=i}$ the weighted population equals
#           the reported population value (i.e. weighed by 1).
#         - This results in a list with four tibbles - one for each
#           $idealCountry_i$. Each tibble contains the estimated HIV reduction
#           in every country in response to a PEPFAR shock in $idealCountry_i$
#           based on diffusion through the trade network of $idealCountry_{i}$.
#         - These tibble results are store in the `results` list as:
#           `idealResponsesFull`
#
#   - Ideal country - cumulative HIV reductions:
#     - Using the values estimated and stored in `idealResponsesFull`,
#       cumulative HIV case reductions are computed that reflect the total LRSS
#       estimated HIV reduction in response to the median PEPFAR per capita
#       aid allocation.
#     - An estimated total cost of the PEPFAR shock allocation for each ideal
#       country: $PEPFAR_{PC\ Shock} \times Population_{Country\ i}$ is also
#       saved as a list:
#         - The LRSS estimates are stored in the `results` list as:
#           `idealResponsesCumulative`
#         - The PEPFAR dollar cost is stored as: `idealPepfarDollarCost`
#
#   - Ideal country - indirect top beneficiaries:
#     - From `idealResponseFull`, the top-10 indirect beneficiary countries +
#       the hypothetical PEPFAR recipient country (`ideal` country) are
#       extracted to a list sorted by total LRSS estimated HIV case reductions.
#     - These estimates are store in the `results` list as: `idealTop10`
#
#   - Ideal country - HIV reduction per 100k
#     - Using the per 100k estimates stored in `results$idealResponsesFull`,
#       compute the cumulative reductions for comparison purposes.

# Ideal recipient country identification:
# - Identify all countries with "High" HIV rates (2 IQR + median)
# - pepfar trade (median value)
# - pepfar recipient status (modal value)
ctry <- d$data %>%
  mutate(hivCat = case_when(
    ihme_hiv100k > 2*IQR(ihme_hiv100k) + median(ihme_hiv100k) ~ "HIV - High",
    .default = "HIV - Low")
  ) %>%
  group_by(cname) %>%
  summarize(ccode       = first(ccode),
            hivCat      = names(which.max(as.list(table(hivCat)))),
            hiv100k     = median(ihme_hiv100k),
            pepfarTrade = median(analysis_tradePepfarPercent),
            pepfarNever = all(analysis_pepfarCat == "PEPFAR - No"),
            .groups     = "keep") %>%
  ungroup

# Identify ideal recipients based on previously listed "ideal" conditions:
results$ideal <- ctry %>%
  filter(pepfarNever,
         hivCat == "HIV - High",
         pepfarTrade < 0.12) %>%
  arrange(pepfarTrade) %>%
  mutate(hiv100kHighThreshold = 2 * IQR(d$data$ihme_hiv100k) +
           median(d$data$ihme_hiv100k),
         hiv100kMedian = median(d$data$ihme_hiv100k))

rm(ctry)


# HIV reduction calculations:
## Ideal country - trade partner specific HIV reductions

# - Create cross-sectional spatial weights matrix using panel trade weights
# - Note, here I use year 2017 because Equatorial Guinea dropped from analysis
#   in 2018 due to missing values on controls.
# - Create PEPFAR shock value: median allocation to PEPFAR recipient countries
w     <- spatial$weights$trade
w     <- w[str_ends(rownames(w), "2017"), str_ends(colnames(w), "2017")]
shock <- median(d$data$pepfarPc[d$data$pepfarPc > 0])

# Store the shock in results for future reference if needed
results$idealPepfarShockUsdPerCapita <- shock

# - Calculate full LRSS HIV reductions among all trade partners with country
#   $ideal_i$ (indirect LRSS spatial effect) as well HIV reductions within
#   country $ideal_i$ itself (direct LRSS spatial effect)
# Calculate responses
results$idealResponsesFull <- lapply(results$ideal$ccode,
                                     effects,
                                     theShock = shock,
                                     w        = w)

# Assign names for organization
names(results$idealResponsesFull) <- results$ideal$cname %>%
  str_remove_all(., "[:punct:]| ")


## Ideal country - cumulative HIV reductions
# - Using the trade-partner specific HIV case reductions estimated in the
#   previous step, calculate the cumulative LRSS HIV case reductions in response
#   to a PEPFAR allocation to country $ideal_i$.
# - Note, aggregating the lower- and upper-bound estimates to produce cumulative
#   lower- and upper-bound estimates produce identical values to those calculated
#   by aggregating for each posterior LRSS estimate and then calculating a quantile.
# - In future, there may be better ways to incorporate posterior uncertainty.
results$idealResponsesCumulative <- lapply(
  names(results$idealResponsesFull), function(x){
    tmp <- results$idealResponsesFull[[x]]
    out <- tmp %>% group_by(effect) %>%
      summarize(across(.cols = c(lb, md, ub), .fns = sum),
                .groups = "keep") %>%
      ungroup %>%
      mutate(cname = x)
  })

names(results$idealResponsesCumulative) <- names(results$idealResponsesFull)

# Total per capita PEPFAR costs based on ideal country population in 2017:
results$idealPepfarDollarCost <- lapply(results$ideal$ccode, function(x){
  pop <- d$data %>% filter(year  == "2017",
                           ccode == x) %>%
    pull(un_popTotal)
  return(pop * shock)
})

names(results$idealPepfarDollarCost) <- names(results$idealResponsesFull)


## Ideal country - indirect top beneficiaries
# - Extract top-10 indirect beneficiaries (in terms of LRSS total HIV case
#   reductions) to a shock of PEPFAR aid in each ideal country plus the direct
#   response of HIV reductions in the ideal country:
results$idealTop10 <- lapply(results$idealResponsesFull, function(x){
  out <- x %>%
    arrange(md) %>%
    mutate(across(.cols = c(lb, md, ub),
                  .fns  = ~ formatC(.x, digits = 0, format = "f"))) %>%
    mutate(target = sprintf("%s: %s [%s, %s]", cname, md, lb, ub))

  direct   <- out %>% filter(effect == "direct")   %>% pull(target)
  indirect <- out %>% filter(effect == "indirect") %>%
    slice(1:10) %>% pull(target)

  out <- c(direct, indirect)

  return(out)
})


## Ideal country - HIV reduction per 100k
# - Calculate LRSS reductions per 100k direct (own unit) and indirect
#   (non-own unit) effects within each ideal PEPFAR target country. This is
#   primarily for validation and comparison purposes. These estimates should
#   closely match those with comparable moderating trade values stored in
#   `results$lrss$effects`
results$idealReductionsPer100k <- lapply(
  results$idealResponsesFull, function(x){
    tapply(x[["reductionPer100k"]], x[["effect"]], sum)
    })


# ------------------------------------- #
# 4 - save ----
save(results, file = here("10-data/03-analysis/04-effects.rdata"))
rm(list = ls())
