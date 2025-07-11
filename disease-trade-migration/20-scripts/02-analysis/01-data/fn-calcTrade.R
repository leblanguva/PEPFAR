calcTrade <- function(rn, w, pepfarRecipients){
  # calcTrade ~ applies to the rowname of a *single-year* spatial weights trade
  # matrix and computes total trade with PEPFAR and non-PEPFAR recipient trade
  # partners. The function returns the percent of the rowname country's trade
  # with PEPFAR recipients

  # rn = trade matrix (w) RowName (must be name ~ need country-unit ccode)

  # w  = trade matrix
  x <- w[rn, ]

  tmp <- tibble(trade   = as.numeric(x),
                partner = names(x)) %>%
    separate(partner, into = c("ccode", "year"), sep = "[.]") %>%
    mutate(pepfar = case_when(ccode %in% pepfarRecipients ~ "pepfar",
                              .default = "notPepfar"))

  tmp <- tmp %>%
    group_by(pepfar) %>%
    summarize(year  = first(year),
              trade = sum(trade)) %>%
    pivot_wider(id_cols     = year,
                names_from  = pepfar,
                values_from = trade) %>%
    mutate(tradePepfarPercent = pepfar / (notPepfar + pepfar),
           pnid = rn) %>%
    rename(tradePepfar = pepfar,
           tradeNotPepfar = notPepfar)

  return(tmp)
}
