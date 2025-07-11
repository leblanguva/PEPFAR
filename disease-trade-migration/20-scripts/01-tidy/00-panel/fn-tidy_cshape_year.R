tidy_cshape_year <- function(yr, quiet = TRUE){
  # simple helper function to iterate over analysis years and:
  # - collect country shapes for year
  # - create identifier variables (pnid, region)
  # - project into Robinson Equal Area
  # - ensure valid geometry of resulting shape

  if(!quiet){cat(sprintf("Working on year: %s\n", yr))}

  tmp <- cshp(date  = as.Date(sprintf("%s-12-31", yr)),
              useGW = FALSE) %>%
    rename(ccode = cowcode,
           cname = country_name) %>%
    mutate(year  = yr,
           pnid  = paste(ccode, yr, sep = "."),
           region   = countrycode(ccode, "cown", "region"),
           region23 = countrycode(ccode, "cown", "region23",
                                  custom_match = c("345" = "Eastern Europe",
                                                   "347" = "Eastern Europe"))) %>%
    select(ccode, cname, year, pnid, region, region23) %>%
    st_transform(., crs = st_crs("+proj=robin")) %>%
    st_make_valid(.) %>%
    st_cast(., to = "MULTIPOLYGON")

  return(tmp)
}
