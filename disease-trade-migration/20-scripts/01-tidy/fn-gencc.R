gencc <- function(data){
  # gencc ~ generate COW country-code
  # applies correction for Yugoslavia
  tmp <- tibble(cname = unique(data[["cname"]])) %>%
    mutate(ccode = countrycode(cname, "country.name", "cown",
                               custom_match = c("Serbia" = 345,
                                                "SRB"    = 345,
                                                "YUG"    = 345))) %>%
    drop_na(ccode)

  data <- left_join(data, tmp, by = "cname") %>% drop_na(ccode)
  return(data)
}
