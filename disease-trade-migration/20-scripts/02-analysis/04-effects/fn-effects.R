effects <- function(target, 
                    w, 
                    theShock = 1, 
                    data     = d$data, 
                    model    = res_main$m3_spatialW1_trade){
  # - The following `effects` function takes a `target` country code such as from 
  #   those stored in `results$ideal$ccode`, a cross-sectional spatial weights 
  #   matrix (`w`), and a `shock` value representative of a realistic PEPFAR per 
  #   capita allocation. It computes the direct and indirect LRSS HIV reductions 
  #   estimated in response to that shock.
  # - A cross-sectional `w` is required as LRSS estimates reflect the final 
  #   response in each analysis unit to a hypothetical exogenous shock and is 
  #   therefore of dimension $n \times n$ by construction.
  
  # target - target country ccode
  # w      - cross-section year subset
  # shock  - pepfar shock to supply lrss function
  
  # Extract spatial (trade) weights from w which describe the intensity of 
  # connection between target_(i) and w_(i_\ne_j)
  w <- w[str_starts(rownames(w), as.character(target)),]
  w <- tibble(
    pnid        = names(w), 
    tradeWeight = as.numeric(w)
  )
  
  # Extract population values from data and join weights from w above.
  # use these weights to construct weighted population estimates
  # for the target country the weighted population equals the obeserved pop
  pops <- data %>% 
    filter(year == "2017") %>% 
    left_join(., w, by = "pnid") %>% 
    select(ccode, un_popTotal, ihme_hiv, ihme_hiv100k, tradeWeight) %>% 
    mutate(popWeighted = case_when(
      ccode == target ~ un_popTotal, 
      ccode != target ~ un_popTotal * tradeWeight
    ))
  
  
  # Using the `results$ideal` country list, extract reported median 
  # pepfar trade (results$ideal$pepfarTrade) to use at the context 
  # conditioning variable to describe the pre-dynamic marginal effect
  # of an additional dollar of pepfar aid. to be used in LRSS calculation
  tgtZvalue <- results$ideal %>% 
    filter(ccode == target) %>% 
    pull(pepfarTrade)
  
  # Calculate estimated LRSS effects. 
  # Results are not tidied (i.e., returned as a list of posterior 
  # LRSS estimates) in order to use each LRSS estimate to calculate 
  # trade-partner-specific case reductions after
  effs <- lrss(obj  = model, 
               z    = tgtZvalue,
               evs  = list("trade" = ev),
               shock= theShock,
               tidy = FALSE) 
  
  # Calculate HIV case reductions (cases, not rates per 100k)
  res <- lapply(pops$ccode, function(x){
    popi = pops %>% filter(ccode == x) %>% pull(popWeighted)
    
    if(x == target){
      out <- (effs$direct / 1e5) * popi 
    } else{
      out <- (effs$indirect / 1e5) * popi
    }
    
    out <- t(quantile(out, probs = c(0.025, 0.50, 0.975))) %>% 
      as_tibble %>% 
      rename(lb = 1, md = 2, ub = 3) %>% 
      mutate(ccode  = x, 
             effect = case_when(x == target ~ "direct", 
                                .default    = "indirect"))
    return(out)
  })
  
  # Tidy res and calculate the percent reduction in observed total HIV
  # cases as well as the predicted rate per 100k which should approximately
  # match those reported in `results$lrss$effects` as a validity check
  res <- res %>% bind_rows() %>% 
    left_join(pops, ., by = "ccode") %>% 
    mutate(reductionPercent = 100 * (md / ihme_hiv),
           reductionPer100k = 1e5 * (md / un_popTotal),
           cname = countrycode(as.numeric(as.character(ccode)),
                               "cown", "country.name")) %>% 
    arrange(md) %>% 
    select(cname, everything(), -ccode)
  
  # Return results
  return(res)
}