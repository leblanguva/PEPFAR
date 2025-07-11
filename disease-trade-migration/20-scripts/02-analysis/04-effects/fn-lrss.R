lrss <- function(obj, withTime = T, z = NULL, evs = NULL,
                 shock = 1,
                 x = "pepfarPc", tidy = TRUE){
  # This function takes a model fit object (list containing fit and vnames)
  # and computes the lrss effect estimate of pepfar dollars on HIV incidence
  # for temporal and spatiotemporal models.

  fit  <- obj$fit
  pars <- rstan::extract(fit)

  wmup <- fit@stan_args[[1]]$warmup
  iter <- fit@stan_args[[1]]$iter
  rng  <- (wmup+1):(iter)

  beta <- pars[["beta"]][rng, ]

  rho_pars <- sum(str_detect(names(pars), "rho"))
  if(rho_pars > 0){
    if(is.null(evs)){stop("Rho found, need eigenvalues")}
    if(rho_pars > 1){stop("This function is not ready for W2 or W3")}
    for(i in 1:rho_pars){
      tmp1 <- paste0("rho", i)
      tmp2 <- paste0("evs", i)
      assign(tmp1, pars[[tmp1]][rng] %>% as.vector)
      assign(tmp2, evs[[i]])
    }
    nn <- length(evs1)
  }

  colnames(beta) <- obj$vnames

  phi <- beta[,"ihme_hiv100kFdLag"]

  # Identify impulse (context conditional if pepfar, beta otherwise)
  if(x == "pepfarPc"){
    if(is.null(z)){stop("z value is required.")}
    bpepfar <- beta[, "pepfarPc"]

    # interaction terms
    bz1   <- beta[, "pepfarPc:analysis_tradePepfarPercent"]
    bz2   <- beta[, "pepfarPc:analysis_tradePepfarPercent2"]
    bz1z2 <- beta[,
                  "pepfarPc:analysis_tradePepfarPercent:analysis_tradePepfarPercent2"]

    # Calculate PRE-dynamic impulse
    bx <- shock * (bpepfar + (bz1 * z) + (bz2 * z^2) + (bz1z2 * z^3))
  } else{
    bx <- shock * beta[, x]
  }

  # Results conditional on dynamics:
  if(rho_pars == 0){
    # Temporal lrss
    eff <- bx / (1 - phi)
    res <- tibble(effect = "total",
                  lower  = quantile(eff, probs = c(0.025)) %>% as.numeric,
                  median = quantile(eff, probs = c(0.500)) %>% as.numeric,
                  upper  = quantile(eff, probs = c(0.975)) %>% as.numeric,
                  zAt    = z)
    life90 <- log(1 - 0.9) / log(phi)
    life90 <- tibble(
      effect = "life90",
      lower  = quantile(life90, probs = c(0.025)) %>% as.numeric,
      median = quantile(life90, probs = c(0.500)) %>% as.numeric,
      upper  = quantile(life90, probs = c(0.975)) %>% as.numeric,
      zAt    = z)

    res <- bind_rows(res, life90)

  } else {
    # Spatiotemporal lrss
    ## gather params
    dd <- tibble(
      bx  = bx,
      phi = phi,
      rho = rho1
    ) %>%
      mutate(life90 = log(1 - 0.9) / log(phi + rho))

    res <- apply(dd, 1, function(x){
      zbx  <- x[["bx"]]
      zphi <- x[["phi"]]
      zrho <- x[["rho"]]

      if(withTime){
        direct   <- (zbx * sum(1 / (1 - (zphi - zrho * evs1)))) / nn
        total    <- zbx / (1 - zphi - zrho)
        indirect <- total - direct

        indirectPercent <- indirect / total
        directPercent   <- 1 - indirectPercent

      } else{
        direct   <- (zbx * sum(1 / (1 - (zrho * evs1)))) / nn
        total    <- zbx / (1 - zrho)
        indirect <- total - direct

        indirectPercent <- indirect / total
        directPercent   <- 1 - indirectPercent
      }

      out <- tibble(direct   = direct,
                    indirect = indirect,
                    total    = total,

                    directPercent   = directPercent,
                    indirectPercent = indirectPercent)

      return(out)
    }) %>%
      bind_rows() %>%
      mutate(life90 = dd$life90)

    if(tidy){
      res <- lapply(res, quantile, probs = c(0.025, 0.500, 0.975)) %>%
        bind_rows(.id = "effect") %>%
        rename(lower = 2, median = 3, upper = 4) %>%
        mutate(zAt = z)
    }
  }
  return(res)
}
