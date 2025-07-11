# ------------------------------------- #
# name   : 02-analysis/05-results-tables
# purpose: this script constructs result tables for regression models and
#          marginal effects estimates
#
# imports:
#   - `10-data/03-analysis/01-analysis-data.rdata`
#     - data with only observations and variables used in regression models
#       Exported from `20-scripts/02-analysis/01-data/default.R`
#   - `10-data/03-analysis/03-fit-main.rdata`
#     - fit regression models -- main
#       Exported from `20-scripts/02-analysis/03-fit/default.R`
#   - `10-data/03-analysis/03-fit-appendix.rdata`
#     - fit regression models -- appendix
#       Exported from `20-scripts/02-analysis/03-fit/default.R`
#   - `10-data/03-analysis/04-effects.rdata`
#     - marginal effects from fit regression models
#       Exported from `20-scripts/02-analysis/04-effects/default.R`
#
# exports:
#   - `30-results/01-tables/05-regressions-main.tex`
#      - main regression results. Bayesian non-spatial and spatial models
#      - Table 3 in draft (note: Table 4 in draft is just a condensed version
#        of this output)
#   - `30-results/01-tables/05-regressions-appendix-bayes.tex`
#      - supplemental Bayesian spatial models with alternative Weight
#       combinations
#      - Table 10 in draft
#   - `30-results/01-tables/05-regressions-appendix-mle.tex`
#      - supplemental MLE spatial regression models (all single W)
#      - Not present in draft
#   - `30-results/01-tables/05-marginal-pepfar.tex`
#      - PEPFAR LRSS marginal effects at PEPFAR trade = (5%, 15%)
#      - Table 5 in draft
#   - '30-results/01-tables/05-ideal-countries.tex'
#      - HIV incidence and trade % with PEPFAR recipients for four ideal
#        pepfar recipients
#      - Table 6 in draft
#   - '05-ideal-cumulative.tex'
#      - estimated cumulative direct and indirect (trade spillover) HIV case
#        (not incidence rate) reductions in response to a representative PEPFAR
#        shock to four "ideal" countries.
#      - Table 7 in draft
#   - '05-ideal-top10-{v1,v2}.tex'
#      - estimated HIV case (not incidence rate) reductions in trading partners
#        with four ideal PEPFAR recipients in response to a representative
#        PEPFAR aid allocation to those ideal recipients. These are the top-10
#        indirect (via trade) beneficiaries in terms of HIV reductions to that
#        PEPFAR allocation.
#      - two identical versions of the table with different formatting (v1,v2)
#        are saved
#      - Table 8 in draft (v2)
#
# sections:
#     0 - setup
#     1 - regression tables
#         - main
#         - appendix Bayesian models
#         - appendix MLE models
#     2 - marginal effects tables
#         - lrss - global estimates
#         - ideal country table
#         - ideal cumulative responses
#         - ideal top 10 beneficiaries


# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(rstan)
library(loo)
library(texreg)
library(kableExtra)

library(here)
i_am("20-scripts/02-analysis/05-results-tables/default.R")

# load data
load(here("10-data/03-analysis/01-analysis-data.rdata")) # Model data
load(here("10-data/03-analysis/03-fit-main.rdata"))      # Fit main mods
load(here("10-data/03-analysis/03-fit-appendix.rdata"))  # Fit appendix mods
load(here("10-data/03-analysis/04-effects.rdata"))       # Model effect/preds

# load functions
source(here("20-scripts/02-analysis/05-results-tables/fn-bsum.R"))


# ------------------------------------- #
# 1 - regression tables ----
## shared options both main and appendix tables
## custom GOF rows - all models have both country and year FEs
gof <- list("FE - Country" = "Yes", "FE - Year" = "Yes")
## custom note for logged variables
cnote <- "%stars\n$\\circ$ denotes logged variable."


## main regression table
tabMain <- lapply(res_main, bsum)
texreg(
  l                  = tabMain,
  custom.coef.map    = as.list(d$vnames),
  custom.gof.rows    = lapply(gof, rep, length(tabMain)),
  custom.model.names = sprintf("[%s]", 1:length(tabMain)),
  custom.header      = list("Non-spatial" = 1:2, "Spatial" = 3:5),
  custom.note        = cnote,

  digits   = 3,
  booktabs = TRUE,
  sideways = TRUE,
  no.margin= TRUE,
  scalebox = 0.75,
  label    = "table:regressions-main",
  caption  = "Main Results",
  file     = here("30-results/01-tables/05-regressions-main.tex"))


## appendix Bayes regression table
tabAppendixBayes <- lapply(res_appendix[1:4], bsum)
tabAppendixBayes$a1_spatialW1_distance@coef.names[19]  <- "rho.distance"
tabAppendixBayes$a2_spatialW1_migration@coef.names[19] <- "rho.migration"
tabAppendixBayes$a3_spatialW2_distance_migration@coef.names[19] <- "rho.distance"
tabAppendixBayes$a3_spatialW2_distance_migration@coef.names[20] <- "rho.migration"
tabAppendixBayes$a4_spatialW2_trade_migration@coef.names[19] <- "rho.trade"
tabAppendixBayes$a4_spatialW2_trade_migration@coef.names[20] <- "rho.migration"

texreg(
  l                  = tabAppendixBayes,
  custom.coef.map    = as.list(d$vnames),
  custom.gof.rows    = lapply(gof, rep, length(tabAppendixBayes)),
  custom.model.names = c("W1 - Distance",
                         "W1 - Migration",
                         "W2 - Distance + Migration",
                         "W2 - Trade + Migration"),
  custom.note        = cnote,

  digits   = 3,
  booktabs = TRUE,
  sideways = TRUE,
  no.margin= TRUE,
  scalebox = 0.75,
  label    = "table:regressions-appendix-bayes",
  caption  = "Supplemental Results - Bayesian models",
  file     = here("30-results/01-tables/05-regressions-appendix-bayes.tex"))

texreg(l = res_appendix$aa_spatialW1_mle,
       custom.coef.map    = as.list(d$vnames),
       custom.gof.rows    = lapply(gof, rep,
                                   length(res_appendix$aa_spatialW1_mle)),
       custom.model.names = str_to_sentence(
         names(res_appendix$aa_spatialW1_mle)
       ),
       custom.note        = cnote,

       digits   = 3,
       booktabs = TRUE,
       sideways = TRUE,
       no.margin= TRUE,
       scalebox = 0.75,
       label    = "table:regressions-appendix-mle",
       caption  = "Supplemental Results - MLE models",
       file     = here("30-results/01-tables/05-regressions-appendix-mle.tex")
)

# clean up
rm(res_main, res_appendix, gof, tabMain, tabAppendixBayes, bsum)


# ------------------------------------- #
# 2 - marginal effects tables ----

## lrss - global estimates PEPFAR aid @ 5% / 15% PEPFAR Trade marginal effects
texreg(
  l        = results$lrssTable,
  custom.model.names = c("Non-Spatial (controls)", "Spatial (W1 - Trade)"),
  digits   = 3,
  booktabs = TRUE,
  label    = "table:maringal-pepfar",
  caption  = "PEPFAR- LRSS Marginal Effects",
  file     = here("30-results/01-tables/05-marginal-pepfar.tex")
)


## ideal country table
results$ideal %>%
  select(cname, hiv100k, pepfarTrade) %>%
  mutate(pepfarTrade = pepfarTrade * 100) %>%
  mutate(across(.cols = c(hiv100k, pepfarTrade),
                .fns  = ~ formatC(.x, format = "f", digits = 2))) %>%
  kbl(format    = "latex",
      booktabs  = TRUE,
      col.names = c("Country",
                    "HIV Incidence (per 100k)",
                    "Trade with PEPFAR recipients (% total trade)")) %>%
  kable_classic(full_width = FALSE) %>%
  save_kable(x    = .,
             file = here("30-results/01-tables/05-ideal-countries.tex"))


## ideal cumulative responses
lapply(c("direct", "indirect"), function(x){
  tmp <- results$idealResponsesCumulative %>%
    bind_rows() %>%
    filter(effect == x) %>%
    mutate(cname = case_match(
      cname,
      "GuineaBissau"     ~ "Guinea Bissau",
      "EquatorialGuinea" ~ "Equatorial Guinea",
      .default = cname
    ))

  out <- createTexreg(
    coef.names = tmp$cname,
    coef       = tmp$md,
    ci.low     = tmp$lb,
    ci.up      = tmp$ub,
    model.name = str_to_sentence(x)
  )
  return(out)
}) %>%
  texreg(
    l        = .,
    digits   = 1,
    booktabs = TRUE,
    label    = "table:ideal-cumulative",
    caption  = "PEPFAR Hypothetical - Cumulative HIV Case Reductions",
    file     = here("30-results/01-tables/05-ideal-cumulative.tex")
)


## ideal top 10 beneficiaries
## formatted in two ways here
## 4-column list table
results$idealTop10 %>%
  bind_cols() %>%
  rename("Guinea Bissau"     = 1,
         "Equatorial Guinea" = 3) %>%
  kbl(format   = "latex",
      booktabs = TRUE,
      linesep  = "") %>%
  kable_classic(full_width = FALSE) %>%
  footnote(general = "Values reflect predicted HIV case reductions. Prediction 95% credible in brackets.") %>%
  save_kable(x    = .,
             file = here("30-results/01-tables/05-ideal-top10-v1.tex"))

## 2x2 table
bind_rows(
  results$idealTop10 %>%
    bind_cols() %>%
    select(1:2) %>%
    rename("a" = 1, "b" = 2),

  results$idealTop10 %>%
    bind_cols() %>%
    select(3:4) %>%
    rename("a" = 1, "b" = 2)
) %>%
  kbl(format   = "latex",
      booktabs = TRUE,
      linesep  = c(rep("",10), "\\addlinespace")) %>%
  kable_classic(full_width = FALSE) %>%
  footnote(general = "Values reflect predicted HIV case reductions. Prediction 95% credible in brackets.") %>%
  save_kable(x    = .,
             file = here("30-results/01-tables/05-ideal-top10-v2.tex"))

rm(list = ls())

