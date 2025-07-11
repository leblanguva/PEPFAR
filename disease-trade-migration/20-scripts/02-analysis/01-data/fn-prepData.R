prepData <- function(data, w){
  # prepData ~ function to quickly return subset data based on unique
  # identifiers (column: pnid ~ "panel id") in W row and column names
  if(!"pnid" %in% colnames(data)){ stop("pnid missing from data.") }
  ids <- rownames(w)
  if("sf" %in% class(data)){data <- data %>% st_drop_geometry}
  data <- data %>% filter(pnid %in% ids)
  return(data)
}
