# ------------------------------------- #
# name   : 0X-xxx
# purpose: this script produces figures based on results estimates
#
# imports:
#   - `10-data/03-analysis/04-effects.rdata`
#     - marginal effects from fit regression models
#       Exported from `20-scripts/02-analysis/04-effects/default.R`
#
# exports:
#   - `30-results/02-figures/06-spatial-effect-pepfar.png`
#      - Long run steady state (lrss) spatial effects (direct, indirect, total)
#        of a representative PEPFAR aid shock on HIV incidence rate reductions
#        across varying levels of trade with other PEPFAR recipients for the
#        hypothetical PEPFAR aid recipient.
#      - Figure 3 in draft
#
# sections:
#     0 - setup
#     1 - lrss spatial marginal


# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)

library(here)
i_am("20-scripts/02-analysis/06-results-figures.R")

# load data
load(here("10-data/03-analysis/04-effects.rdata")) # Model effect/preds


# ------------------------------------- #
# 1 - lrss spatial marginal ----
# context conditional (by PEPFAR trade) LRSS spatial marginal effects plot
p1 <- ggplot(data = results$lrss$effects %>%
               mutate(effect = str_to_sentence(effect)) %>%
               filter(model == "Spatial - W1 Trade"), aes(x = zAt)) +
  geom_hline(aes(yintercept = 0), color = "red",
             linetype = "dotted", linewidth = 0.1) +
  geom_ribbon(aes(ymin = lower, ymax = upper), alpha = 0.4) +
  geom_line(aes(y = median), linewidth = 0.1) +
  facet_wrap(~effect, ncol = 3) +
  theme(
    panel.background = element_rect(fill      = NA,
                                    color     = "black",
                                    linewidth = 0.2),
    strip.background = element_rect(fill      = "gray80",
                                    color     = "black",
                                    linewidth = 0.2),
    axis.ticks = element_line(color     = "black",
                              linewidth = 0.1),
    text = element_text(size = 10)
  ) +
  scale_x_continuous(labels = function(x){x * 100}) +
  labs(
    y = "HIV Indcidence (rate per 100k)",
    x = "PEPFAR recipient trade with other PEPFAR countries (%)"
  )

ggsave(plot = p1,
       filename = here("30-results/02-figures/06-spatial-effect-pepfar.png"),
       width    = 8.0,
       height   = 6.5,
       dpi      = 350)

rm(list = ls())
