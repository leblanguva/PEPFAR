fit <- function(formula, data, model,
                warmup     = 2e3,
                iterations = 5e3,
                weights    = NULL,
                evals      = NULL){
  require(rstan)

  # Convenience function to take an input formula, construct model
  # data list, and fit stan models. Works with spatial models too

  # dd <- model.frame(formula, data) %>% tibble
  # id <- data$pnid[!rownames(data) %in% na.action(dd)]

  # Form model frame
  data <- model.frame(formula, data)

  # Drop unused factor levels from data to prevent incorrect param explosions
  data <- data %>% mutate(across(.cols = where(is.factor),
                                 .fns  = fct_drop))

  y <- data[,1] %>% unlist %>% as.vector
  X <- model.matrix(formula, data)

  md <- list(n = nrow(X),
             k = ncol(X),
             y = y,
             X = X)
  pars <- c("beta", "log_lik")

  if(!is.null(weights)){
    md <- c(md, weights, evals)

    pars <- c(pars,
              paste0("rho", 1:length(weights)))
  }

  res <- sampling(object  = model,
                  data    = md,
                  warmup  = warmup,
                  iter    = iterations,
                  chains  = 2,
                  cores   = 2,
                  refresh = 0, # do not print chain iteration output
                  init    = 0,
                  pars    = pars,
                  # To resolve any divergent transition warnings:
                  control = list("stepsize"    = 0.5,
                                 "adapt_delta" = 0.9))

  out <- list(
    "fit"    = res,
    "vnames" = colnames(X),
    "nobs"   = nrow(X)
  )

  return(out)
}
