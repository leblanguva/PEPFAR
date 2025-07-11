wrs <- function(m){
  # wrs ~ row standardize values in w
  m <- apply(m, 1, function(x){x / sum(x)})
  m <- t(m)
  return(m)
}
