data {
  int<lower=0>  n;            // number of observations
  int<lower=0>  k;            // number of predictors
  vector[n]     y;            // outcome vector
  matrix[n, k]  X;            // matrix of predictors
  matrix[n, n]  W1;           // matrix of neighbors, w1
  matrix[n, n]  W2;           // matrix of neighbors, w2

  vector[n] evals1;           // spatial weight eigenvalues for effect calcs
  vector[n] evals2;           // spatial weight eigenvalues for effect calcs
}
transformed data {
  matrix[n, k] Q_ast;
  matrix[k, k] R_ast;
  matrix[k, k] R_ast_inverse;

  // thin and scale the QR decomposition
  Q_ast = qr_thin_Q(X) * sqrt(n - 1);
  R_ast = qr_thin_R(X) / sqrt(n - 1);
  R_ast_inverse = inverse(R_ast);
  
  // Spatial lag approximations
  matrix[n, 6] slag1;
  matrix[n, 6] slag2;
  vector[6] lags;

  for(i in 1:6){
    slag1[,i] = (W1.^i) * y;
    slag2[,i] = (W2.^i) * y;
    lags[i]  = i;
  };
}
parameters {
  vector[k] theta;                                  // coefficients on qast
  real<lower=min(evals1), upper=max(evals1)> rho1;  // spatial lag term, w1
  real<lower=min(evals2), upper=max(evals2)> rho2;  // spatial lag term, w2
  real<lower=0> sigma;                              // error scale
}
model {
  rho1  ~ normal(0, 1);
  rho2  ~ normal(0, 1);
  theta ~ normal(0, 1);

  y   ~ normal(
  (slag1 * rho1^lags) +
  (slag2 * rho2^lags) +
  (Q_ast * theta) , sigma);  // likelihood
}
generated quantities {
  vector[k] beta;
  beta = R_ast_inverse * theta; // coefficients on x
  
  real log_lik[n];
  for (i in 1:n) {
    log_lik[i] = normal_lpdf(y[i] | (slag1[i] * rho1^lags) + (slag2[i] * rho2^lags) + (X[i] * beta) , sigma);
  }
  
  //vector[k] direct;
  //vector[k] indirect;
  //vector[k] total;
  
  //direct   = (beta * sum(1 ./ (1 - (rho1 * evals1 + rho2 * evals2)))) / n;
  //total    = direct / (1 - (rho1 + rho2));
  //indirect = total - direct;
}
