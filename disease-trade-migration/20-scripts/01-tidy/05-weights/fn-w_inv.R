w_inv <- function(m){
  # Note - to more heavily weigh countries with shared borders, this function
  #        recodes neighbors with 0 distance as 1 so their inverse distance
  #        measure is preserved as 1. Own unit (diagonal) values remain 0.
  m <- 1/m
  m[is.infinite(m)] <- 1
  diag(m) <- 0

  return(m)
}
