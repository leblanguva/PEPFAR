w_dyad <- function(data,
                   yr,
                   name_variable,
                   name_origin      = "pnid_o",
                   name_destination = "pnid_d",
                   verbose = TRUE,
                   zero_na = TRUE){
  # Create spatial weights matrix from dyadic panel data.
  # Does NOT compute row-standardized weights. Listwise variable
  # deletion will change the included observations necessitating a
  # recalculation of row-standardized values.
  name_variable    <- rlang::ensym(name_variable)
  name_origin      <- rlang::ensym(name_origin)
  name_destination <- rlang::ensym(name_destination)

  if(verbose){
    cat(sprintf("\14Working on year: %s", yr))
  }

  tmp <- data %>%
    filter(year == yr) %>%
    arrange(as.numeric(ccode_d), as.numeric(ccode_o))

  w <- tmp %>%
    pivot_wider(data        = .,
                id_cols     = !!name_destination,
                names_from  = !!name_origin,
                values_from = !!name_variable) %>%
    column_to_rownames(., var = as.character(name_destination)) %>%
    as.matrix

  # Ensure diagonal of w equals 0
  diag(w) <- 0

  # Replace cells with no values (no dyadic flow) with zero
  if(zero_na){w[is.na(w)] <- 0}

  return(w)
}
