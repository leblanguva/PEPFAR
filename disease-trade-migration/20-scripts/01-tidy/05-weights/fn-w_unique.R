w_unique <- function(yr, wlist = ws, tidy_w = FALSE){
  # w_unique ~ returns ids common across all weights per year

  # Grab all matrices for year
  w_yr <- wlist %>% purrr::map(., yr)

  # List of all rownames in year
  w_nm <- lapply(w_yr, rownames)

  # Common rownames in year
  w_cm <- Reduce(intersect, w_nm)

  if(tidy_w){
    lapply(w_yr, function(w){
      return(w[rownames(w) %in% w_cm, colnames(w) %in% w_cm])
    })
  } else{
    return(w_cm)
  }
}
