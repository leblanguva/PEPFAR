wsub <- function(w, ids, rs = TRUE){
  # wsub ~ subset W to match ids in data. rs = row standardize w
  w   <- w[ids,ids]
  if(rs){w <- wrs(w)}
  return(w)
}
