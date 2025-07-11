w_dist <- function(data,
                   yr,
                   id      = "pnid",
                   inverse = TRUE,
                   verbose = TRUE){
  # Create spatial weights matrix based on spatial distance.
  # Does NOT compute row-standardized weights. Listwise variable
  # deletion will change the included observations necessitating a
  # recalculation of row-standardized values.

  if(verbose){
    cat(sprintf("\14Working on year: %s", yr))
  }

  tmp_d <- data %>% filter(year == !!yr)

  res <- st_distance(tmp_d)
  units(res) <- NULL

  # Inverse distances
  if(inverse){res <- w_inv(res)}

  # Set index names
  rownames(res) <- colnames(res) <- tmp_d[[id]]

  return(res)
}
