# ------------------------------------- #
# name   : 02-analysis/02-descriptive
# purpose: this script constructs descriptive statistics including:
#          - a 2x2 table of observations proportions
#            (PEPFAR recipients) x (% trade with PEPFAR recipients)
#
#          - descriptive statistics for variables in regression models and
#            table exports of these descriptive stats.
#
#          - a bivariate map of trade (general, not PEPFAR specific) and HIV
#            incidence rates
#
# imports:
#   - `10-data/03-analysis/01-analysis-data.rdata`
#     - analysis data subset containing only observations and variables used
#       in regression models
#       Exported from `20-scripts/02-analysis/01-data.R`
#   - `10-data/02-tidy/00-panel.rds`
#     - spatial data frame of all countries for mapping
#       Exported from `20-scripts/01-tidy/00-panel.R`
#
# exports:
#   - `30-results/01-tables/02-descriptive-2x2.tex`
#      - a table of PEPFAR recipients (Yes/No) by trade % with PEPFAR recipients
#        (high/low). high/low PEPFAR trade cutoff determined using median
#      - Table 1 in draft
#      - NOTE - relative to the version in the draft, I use a lower (more
#        conservative) PEPFAR trade cutoff here resulting in slightly different
#        table values.
#        In the draft the cutoff is:
#          - (median(PEPFAR trade) + InterQuartileRange(PEPFAR trade))
#        Now, here it is:
#          - (median(PEPFAR trade))
#   - `30-results/01-tables/02-descriptive-2x2-ttest.txt`
#      - text document containing difference-of-means test for HIV incidence
#        reductions between non-PEPFAR recipients with high/low trade with
#        PEPFAR recipients
#      - Not present in draft
#   - `30-results/02-figures/02-trade-cutoff.png`
#      - figure evaluating sensitivity of cutoff chosen for 2x2 above.
#      - presents mean and 95% ci of HIV incidence in countries across a range
#        of representative trade % with PEPFAR recipient countries
#      - Figure 1 in draft
#   - `30-results/02-figures/02-biplot-tradeHiv.png`
#      - a bivariate choropleth map of HIV incidence and general trade volume
#      - Figure 2 in draft
#   - `30-results/01-tables/02-descriptive-main.tex`
#      - descriptive statistics for primary variables (HIV, PEPFAR)
#      - Table 2 in draft
#   - `30-results/01-tables/02-descriptive-appendix.tex`
#      - descriptive statistics for control variables
#      - Table 9 in draft
#
# sections:
#     0 - setup
#     1 - 2x2 construction
#     2 - cutoff analysis
#     3 - bivariate map
#     4 - descriptive statistics


# ------------------------------------- #
# 0 - setup ----

# clear environment
rm(list = ls())

# load packages
library(tidyverse)
library(sf)
library(countrycode)
library(kableExtra)
library(biscale)
library(cowplot)

library(here)
i_am("20-scripts/02-analysis/02-descriptive.R")

# load data
load(here("10-data/03-analysis/01-analysis-data.rdata"))
pnl <- read_rds(here("10-data/02-tidy/00-panel.rds"))


# ------------------------------------- #
# 1 - 2x2 construction ----
# Using a cutoff 1 IQR deviation above variable median
# tradeCut <- median(d$data$analysis_tradePepfarPercent) +
#   IQR(d$data$analysis_tradePepfarPercent)
tradeCut <- median(d$data$analysis_tradePepfarPercent)

# Extract groups
tradeHiPepNo <- d$data %>%
  filter(analysis_pepfarCat == "PEPFAR - No" &
           analysis_tradePepfarPercent >= tradeCut) %>%
  select(cname, ihme_hiv100kFd)

tradeLoPepNo <- d$data %>%
  filter(analysis_pepfarCat == "PEPFAR - No" &
           analysis_tradePepfarPercent <  tradeCut) %>%
  select(cname, ihme_hiv100kFd)

tradeHiPepYa <- d$data %>%
  filter(analysis_pepfarCat == "PEPFAR - Yes" &
           analysis_tradePepfarPercent >= tradeCut) %>%
  select(cname, ihme_hiv100kFd)

tradeLoPepYa <- d$data %>%
  filter(analysis_pepfarCat == "PEPFAR - Yes" &
           analysis_tradePepfarPercent <  tradeCut) %>%
  select(cname, ihme_hiv100kFd)


fx <- function(quadrant, tex_tidy = TRUE){
  # function tidies trade means and CIs across trade / pepfar-receipt
  # groups for paper 2x2 table
  tmp      <- t.test(quadrant$ihme_hiv100kFd)
  the_mean <- tmp$estimate %>% as.numeric
  the_ci   <- tmp$conf.int %>% as.numeric

  countries <- length(unique(as.character(quadrant$cname)))
  obs       <- length(quadrant$cname)

  if(tex_tidy){
    the_mean <- the_mean %>% formatC(x = ., format = "f", digits = 3)
    the_ci   <- the_ci   %>% formatC(x = ., format = "f", digits = 3)
    the_ci   <- sprintf("[%s, %s]", the_ci[1], the_ci[2])
    obs      <- sprintf("Observations: %s", obs)

    out <- tibble(est       = the_mean,
                  ci        = the_ci,
                  obs       = obs)
  } else{
    out <- tibble(est   = the_mean,
                  ci.lo = the_ci[1],
                  ci.hi = the_ci[2],
                  countries    = countries,
                  observations = obs)
  }
  return(out)
}

twoBytwo <- list(
  q1 = list("pepfar" = "No",
            "trade"  = "Low",
            "zval"   = fx(tradeLoPepNo)),
  q2 = list("pepfar" = "Yes",
            "trade"  = "Low",
            "zval"   = fx(tradeLoPepYa)),
  q3 = list("pepfar" = "No",
            "trade"  = "High",
            "zval"   = fx(tradeHiPepNo)),
  q4 = list("pepfar" = "Yes",
            "trade"  = "High",
            "zval"   = fx(tradeHiPepYa))
) %>% bind_rows() %>%
  unnest(cols = zval)

twoBytwo %>%
  pivot_longer(data = .,
               cols = c(est, ci, obs),
               names_to = "estimate",
               values_to = "val") %>%
  pivot_wider(data = .,
              id_cols = c(pepfar, estimate),
              names_from = trade,
              values_from = val) %>%
  select(-estimate) %>%
  mutate(ylab = "PEPFAR Recipient") %>%
  relocate(ylab, .before = everything()) %>%
  kbl(x         = .,
      col.names = c(".", "..", "Low", "High"),
      # nb "." and ".." are placeholder column names. will not work otherwise.
      booktabs  = TRUE,
      format    = "latex") %>%
  collapse_rows(columns = 1:2, valign = "middle") %>%
  add_header_above(c("","", "Trade with PEPFAR Recipients" = 2)) %>%
  save_kable(., file = here("30-results/01-tables/02-descriptive-2x2.tex"))


# T-test : among NON-Pepfar recipients, difference in mean HIV between
#          countries with High and Low trade with pepfar recipients
tradeTest <- bind_rows(
  tradeHiPepNo %>% mutate(class = "PEPFAR Trade - High"),
  tradeLoPepNo %>% mutate(class = "PEPFAR Trade - Low")
)
res_hivPepfarTTest <- t.test(tradeTest$ihme_hiv100kFd ~ tradeTest$class)

tl <- t.test(tradeLoPepNo$ihme_hiv100kFd)
tl <- rnorm(1e3, mean = tl$estimate, sd = tl$stderr)
th <- t.test(tradeHiPepNo$ihme_hiv100kFd)
th <- rnorm(1e3, mean = th$estimate, sd = th$stderr)

diff_est <- quantile(replicate(n = 1e3, expr = {sample(th, 1) - sample(tl, 1)}),
                     probs = c(0.025, 0.500, 0.975)) %>%
  as.numeric %>%
  round(., 3)

# Correlation between trade with pepfar and hiv incidence
res_hivPepfarCorrTest <- cor.test(d$data$ihme_hiv100kFd,
                                  d$data$analysis_tradePepfarPercent)


sink(file = here("30-results/01-tables/02-descriptive-2x2-ttest.txt"))
cat(paste("T-test : among NON-Pepfar recipients, is the difference in the",
          "change in HIV incidence rate per 100k (hiv incidence first-diff.)",
          "statistically significantly different between countries with High",
          "or Low trade with PEPFAR recipients? T-test result:\n"))
res_hivPepfarTTest
cat(sprintf(paste("\n\nAmong non-PEPFAR recipients, HIV incidence decreased faster",
                  "in countries with HIGH trade with PEPFAR recipients",
                  "(mean high: %s) than in countries with LOW trade with PEPFAR",
                  "recipients (mean low: %s).\n\n"),
            round(as.numeric(res_hivPepfarTTest$estimate[1]), 3),
            round(as.numeric(res_hivPepfarTTest$estimate[2]), 3)))
cat(sprintf(paste("The mean difference in HIV incidence reduction between",
                  "Non-PEPFAR recipients who had high trade with PEPFAR",
                  "recipients and those with low trade with PEPFAR",
                  "recipieints is %s [95%% ci: %s, %s]\n\n"),
            diff_est[2], diff_est[1], diff_est[3]))

cat(paste("Correlation between HIV incidence rate change (first diff.) and",
          "PEPFAR trade percent:\n"))
res_hivPepfarCorrTest
sink()

# Clean up
rm(tradeLoPepNo, tradeLoPepYa,
   tradeHiPepNo, tradeHiPepYa,
   tradeTest,
   res_hivPepfarCorrTest, res_hivPepfarTTest,
   fx, diff_est, tl, th)


# ------------------------------------- #
# 2 - cutoff analysis ----
trade_cutoff_range <- seq(0.01, 0.3, 0.01)

res <- lapply(trade_cutoff_range, function(x){
  tradeHiPepNo <- d$data %>%
    filter(analysis_pepfarCat == "PEPFAR - No" &
             analysis_tradePepfarPercent >= x) %>%
    pull(ihme_hiv100kFd)

  tradeLoPepNo <- d$data %>%
    filter(analysis_pepfarCat == "PEPFAR - No" &
             analysis_tradePepfarPercent <  x) %>%
    pull(ihme_hiv100kFd)

  tt <- t.test(tradeHiPepNo, tradeLoPepNo)

  pt <- diff(rev(tt$estimate))
  ci <- as.numeric(tt$conf.int)

  res<- tibble(
    pt = as.numeric(pt),
    lb = as.numeric(ci[1]),
    ub = as.numeric(ci[2]),
    x  = x
  )
})

res <- res %>% bind_rows()

res <- res %>%
  mutate(class = case_when(
    x == trade_cutoff_range[which.min(abs(trade_cutoff_range - tradeCut))] ~
      "2x2 cutoff value", .default = NA_character_))

p1 <- ggplot(res, aes(x = x, y = pt, color = class)) +
  geom_errorbar(aes(ymin = lb, ymax = ub), linewidth = 0.2) +
  geom_point(aes(y = pt), size = 0.5) +
  scale_color_manual(values = c(scales::hue_pal()(1)),
                     breaks = c("2x2 cutoff value")) +
  scale_x_continuous(labels = function(x){x * 100}) +
  theme(
    panel.background = element_rect(fill  = NA,
                                    linewidth  = 0.1,
                                    color = "black"),
    panel.grid.major.y = element_line(linetype = "dotted",
                                      linewidth= 0.1,
                                      color    = "black"),
    axis.ticks = element_line(color = "black", linewidth = 0.1),
    text = element_text(size = 10),
    legend.position = "bottom",
    legend.title    = element_blank()
  ) +
  labs(y = "HIV incidence (FD, per 100k)",
       x = "Trade with PEPFAR recipients (% total annual trade)")

p1

ggsave(filename = here("30-results/02-figures/02-trade-cutoff.png"),
       plot     = p1,
       width    = 8.00,
       height   = 4.00,
       units    = "in",
       dpi      = 300)

# Clean up
rm(p1, res, two_by_value, twoBytwo, trade_cutoff_range, tradeCut)


# ------------------------------------- #
# 3 - bivariate map ----
index <- function(x){
  out <- (last(x) / first(x)) * 100
  return(out)
}

dd <- d$data %>%
  select(ccode, year,
         ihme_hiv100k,
         ihme_hiv100kFd,
         pepfarPc, pepfar, oecd_disStdhivAid2020usdPc,
         analysis_wTrade,
         analysis_tradePepfarPercent) %>%
  arrange(ccode, year)

dmap <- dd %>%
  group_by(ccode) %>%
  summarize(
    hiv       = mean(ihme_hiv100kFd),
    trade     = index(analysis_wTrade),
    pepfar    = mean(pepfarPc, na.rm = TRUE),
  ) %>%
  ungroup %>%
  mutate(ccode = as.integer(as.character(ccode)))

dmap <- pnl %>%
  filter(year == max(year)) %>%
  select(ccode) %>%
  left_join(., dmap, by = "ccode")

# Create bi-variate map class
dmap <- bi_class(dmap, x = trade, y = hiv, style = "quantile", dim = 3)

# Create bi-variate legend
legd <- bi_legend(pal = "GrPink",
                  dim = 3,
                  xlab = "Trade ",
                  ylab = "HIV ",
                  size = 6)

p1 <- ggplot() +
  geom_sf(data = dmap,
          mapping = aes(fill = bi_class),
          color = "white", size = 0.1, show.legend = FALSE) +
  geom_sf(data = dmap %>% filter(pepfar > 0),
          aes(color = "PEPFAR recipient"),
          linewidth = 0.15,
          fill = "transparent", show.legend = FALSE) +
  bi_scale_fill(pal = "GrPink", dim = 3) +
  bi_theme() +
  scale_color_manual(values = c("gray40")) +
  theme(plot.margin = margin(-0.5, 0, -0.5, -0.5, "inches"))

p2 <- ggdraw() +
  draw_plot(p1, 0, 0, 1, 1) +
  draw_plot(legd, 0.1, 0.1, 0.2, 0.2)

p2

ggsave(filename = here("30-results/02-figures/02-biplot-tradeHiv.png"),
       plot     = p2,
       width    = 6.50,
       height   = 3.50,
       units    = "in",
       dpi      = 350)

rm(dd, dmap, legd, p1, p2, index)


# ------------------------------------- #
# 4 - descriptive statistics ----
dd <- model.frame(d$form$controls, d$data)

# compute descriptive statistics for all variables
dsum <- dd %>%
  mutate(across(.cols = where(is.factor),
                .fns  = fct_drop)) %>%
  summarize(across(.cols = !c(cname, year),
                   .fns  = list(Mean = mean,
                                SD   = sd,
                                Min  = min,
                                Max  = max),
                   .names= "{.col}.{.fn}")) %>%
  pivot_longer(data      = .,
               cols      = everything(),
               names_to  = c("var", "stat"),
               names_sep = "[.]",
               values_to = "val") %>%
  pivot_wider(data        = .,
              names_from  = stat,
              values_from = val) %>%
  mutate(Variable = recode(var, !!!c(d$vnames))) %>%

  # Drop variables used in modeling but not needed for descriptive statistics
  filter(
    !var %in% c("analysis_tradePepfarPercent2", "ihme_hiv100kFdLag")
  )

# extract main variables for main descriptive statistics table
dsumMain <- dsum %>%
  filter(var %in% c("ihme_hiv100kFd",
                    "pepfarPc",
                    "analysis_tradePepfarPercent")) %>%
  select(Variable, Mean:Max)

# extract remaining variables for appendix descriptive statistics table
dsumAppen <- dsum %>%
  filter(!var %in% c("ihme_hiv100kFd",
                     "pepfarPc",
                     "analysis_tradePepfarPercent")) %>%
  select(Variable, Mean:Max)


# produce and save latex descriptive statistics tables
kable(x         = dsumMain,
      format    = "latex",
      digits    = 3,
      booktabs  = TRUE,
      label     = "table:descriptive-main",
      caption   = "Descriptive statistics",
      col.names = c("", colnames(dsumMain)[2:ncol(dsumMain)])) %>%
  kable_classic(full_width = FALSE) %>%
  save_kable( file = here("30-results/01-tables/02-descriptive-main.tex") )

kable(x         = dsumAppen,
      format    = "latex",
      digits    = 3,
      booktabs  = TRUE,
      escape    = FALSE,
      linesep   = "",
      label     = "table:descriptive-app",
      caption   = "Descriptive statistics",
      col.names = c("", colnames(dsumMain)[2:ncol(dsumMain)])) %>%
  kable_classic(full_width = FALSE) %>%
  footnote(general = "${\\\\circ}$ denotes logged variable.",
           escape  = FALSE) %>%
  save_kable( file = here("30-results/01-tables/02-descriptive-appendix.tex") )

rm(list = ls())
