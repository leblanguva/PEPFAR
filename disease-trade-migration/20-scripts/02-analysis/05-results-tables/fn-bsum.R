bsum <- function(fit_object,
                 texreg    = TRUE,
                 omit_fes  = TRUE){
  # bsum ~ returns a tidy Bayes model SUMmary with correctly matched
  #        input variable names. Provides option for subsetting spatial
  #        models to return parameter estimates (beta) or spatial
  #        effects ("direct", "indirect" or "total")
  #
  # Output can be one of tibble (texreg = FALSE) or texreg object

  # Extract relevant objects from model fit:
  model <- fit_object$fit
  nobs  <- fit_object$nobs
  vnames<- fit_object$vnames

  est_names <- c("beta", "rho")

  # Create variable name tibble for id joining (ids based on column number)
  var_names <- tibble(var_name = vnames) %>%
    mutate(par_id = as.character(1:n()))

  # Summarize model output
  out <- summary(model)$summary %>%
    as.data.frame %>%
    rownames_to_column(., var = "par") %>%
    filter(str_starts(par, paste(est_names, collapse = "|"))) %>%
    mutate(par_id = case_when(
      !str_detect(par, "rho") ~ str_extract(par, pattern = "[0-9]{1,3}"),
      .default = NA_character_
    ))

  # Join model input variable names
  out <- left_join(out, var_names, by = "par_id") %>%
    mutate(var_name = case_when(
      (is.na(var_name) & str_detect(par, "rho")) ~ par,
      .default = var_name
    ))

  # Subset relevant table columns
  out <- out %>%
    janitor::clean_names() %>%
    select(var_name, mean, x2_5_percent, x97_5_percent)

  # Drop FEs if desired
  if(omit_fes){
    out <- out %>%
      filter(!str_starts(var_name, "region|cname|ccode|year"))
  }

  # Extract log-likelihood and calculate waic
  logLik  <- extract_log_lik(stanfit = model)
  # r_eff    <- relative_eff(exp(log_lik), cores = 2)
  # est_loo  <- loo(log_lik, r_eff = r_eff, cores = 2)
  estWaic <- waic(logLik)
  estWaic <- estWaic$estimates["waic", "Estimate"]
  logLik  <- mean(rowSums(logLik))

  # Create texreg object if desired
  if(texreg){
    out <- createTexreg(
      coef.names = out$var_name,
      coef       = out$mean,
      ci.low     = out$x2_5_percent,
      ci.up      = out$x97_5_percent,
      gof.names  = c("Log lik.", "WAIC", "N"),
      gof        = c(logLik, estWaic, nobs),
      gof.decimal= c(T, T, F)
    )
  }
  return(out)
}
