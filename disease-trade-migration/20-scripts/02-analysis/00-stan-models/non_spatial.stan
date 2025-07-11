data {
  int<lower=0>  n;            // number of observations
  int<lower=0>  k;            // number of predictors
  vector[n]     y;            // outcome vector
  matrix[n, k]  X;            // matrix of predictors
}
transformed data {
  matrix[n, k] Q_ast;
  matrix[k, k] R_ast;
  matrix[k, k] R_ast_inverse;

  // thin and scale the QR decomposition
  Q_ast = qr_thin_Q(X) * sqrt(n - 1);
  R_ast = qr_thin_R(X) / sqrt(n - 1);
  R_ast_inverse = inverse(R_ast);
}
parameters {
  vector[k] theta;              // coefficients on qast
  real<lower=0> sigma;          // error scale
}
model {
  theta ~ normal(0, 1);

  y ~ normal(Q_ast * theta , sigma);  // likelihood
}
generated quantities {
  vector[k] beta;
  beta = R_ast_inverse * theta; // coefficients on x
  
  real log_lik[n];
  for (i in 1:n) {
    log_lik[i] = normal_lpdf(y[i] | X[i] * beta, sigma);
  }
}
