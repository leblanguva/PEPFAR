gencc <- function(data, src, src_type = "iso3c"){
  # gencc ~ generate COW country-code
  # applies correction for Yugoslavia
  # a modified version of the genncc command in the 01-tidy directory used when
  # constructing spatial weights
  tmp <- tibble(x = unique(data[[src]])) %>%
    mutate(ccode = countrycode(x, src_type, "cown",
                               custom_match = c("Serbia" = 345,
                                                "SRB"    = 345,
                                                "YUG"    = 345))) %>%
    drop_na(ccode)
  data <- left_join(data, tmp, by = setNames("x", src)) %>% drop_na(ccode)
  return(data)
}
