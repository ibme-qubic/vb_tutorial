#!/usr/bin/env python
# coding: utf-8

# Stochastic Variational Bayes - example nonlinear model
# ==============================================
# 
# This notebook implements stochastic variational Bayes for a nonlinear model. The model we will use is a bi-exponential model, i.e. we will assume our data reflects a time-dependent signal of the following form:
# 
# $$S_{true}(t) = A_1 e^{-R_1t} + A_2 e^{-R_2t}$$
# 
# However the actual time dependent signal $S(t)$ will be affected by additive Gaussian noise, so will have the distribution:
# 
# $$P(S(t)) = \frac{\sqrt{\beta}}{\sqrt{2\pi}} \exp{\bigg(-\frac{\beta}{2} (S(t) - S_{true}(t))^2}\bigg)$$
# 
# Given $S(t)$ our aim will be to infer the values of $A_1$, $A_2$, $R_1$, $R_2$ and $\beta$.
# 
# Here's how we can generate some sample data from this model in Python:

# In[ ]:


import numpy as np

# Ground truth parameters
# We infer the precision, BETA, but it is useful to
# derive the variance and standard deviation from it
A1_TRUTH = 10.0
A2_TRUTH = 10.0
R1_TRUTH = 10.0
R2_TRUTH = 1.0
BETA_TRUTH = 1.0
VAR_TRUTH = 1/BETA_TRUTH
STD_TRUTH = np.sqrt(VAR_TRUTH)

# Observed data samples are generated by Numpy from the ground truth
# Gaussian distribution. Reducing the number of samples should make
# the inference less 'confident' - i.e. the output variances for
# MU and BETA will increase
N = 200
T = np.linspace(0, 5, N)

DATA_CLEAN = A1_TRUTH * np.exp(-R1_TRUTH * T) + A2_TRUTH * np.exp(-R2_TRUTH*T)
DATA = DATA_CLEAN + np.random.normal(0, STD_TRUTH, [N])
print("Data samples are:")
print(DATA)


# We can plot this data to illustrate the true signal (green line) and the measured data (red crosses):

# In[ ]:


from matplotlib import pyplot as plt
plt.figure()
plt.plot(DATA, "rx")
plt.plot(DATA_CLEAN, "g")


# As with the single Gaussian example we will use a multivariate normal distribution as our prior and approximate posterior distributions. 
# 
# One difference here is that we will choose to infer the log of the decay rate parameters $R_1$ and $R_2$. This is because if these parameters are allowed to become negative the model prediction will become an exponential growth and can easily lead to numerical errors.
# 
# We will still choose our priors to be relatively uninformative as follows:
# 

# In[ ]:


a0 = 1.0
v0 = 100000.0
r0 = 0.0
u0 = 10.0
b0 = 0.0
w0 = 10.0
print("Priors: Amplitude mean=%f, variance=%f" % (a0, v0))
print("        Log decay rate mean=%f, variance=%f" % (r0, u0))
print("        Log noise variance mean=%f, variance=%f" % (b0, w0))


# The posterior will be defined in the same way as for the single Gaussian example, however we need to account for the increased number of parameters we are inferring. We will initialize the posterior with the prior values but with reduced initial variance to prevent problems with generating a representative posterior sample. Remember that the decay rates (and the noise) are being inferred as their log-values so the prior mean of 0 translates into a value of 1.

# In[ ]:


import tensorflow as tf

# Number of parameters - 4 for the biexponential + noise
NUM_PARAMS = 4 + 1

data = tf.constant(DATA, dtype=tf.float32)
prior_means = tf.constant([a0, r0, a0, r0, b0], dtype=tf.float32)
prior_covariance = tf.diag(tf.constant([v0, u0, v0, u0, w0], dtype=tf.float32))

post_means_init = prior_means
post_covariance_init = np.identity(NUM_PARAMS, dtype=np.float32)

chol_off_diag = tf.Variable(np.zeros(post_covariance_init.shape), dtype=tf.float32)
# Comment in this line if you do NOT want to infer parameter covariances
#chol_off_diag = tf.constant([[0, 0], [0, 0]], dtype=tf.float32)
chol_log_diag = tf.Variable(tf.log(tf.diag_part(post_covariance_init)), dtype=tf.float32)
chol_diag = tf.diag(tf.sqrt(tf.exp(chol_log_diag)))
post_covariance_chol = tf.add(chol_diag, tf.matrix_band_part(chol_off_diag, -1, 0))

post_covariance = tf.matmul(tf.transpose(post_covariance_chol), post_covariance_chol)
post_means = tf.Variable(post_means_init, dtype=tf.float32)

sess = tf.Session()
sess.run(tf.initialize_all_variables())
print("Initial posterior mean: %s" % sess.run(post_means))
print("Initial posterior covariance:\n%s" % sess.run(post_covariance))


# The code to generate a posterior sample is unchanged except for the number of parameters:

# In[ ]:


# Number of samples from the posterior
S=5

# eps is a sample from a Gaussian with mean 0 and variance 1
eps = tf.random_normal((NUM_PARAMS, S), 0, 1, dtype=tf.float32)

# Start off each sample with the current posterior mean
# post_samples is now a tensor of shape [NUM_PARAMS, n_samples]
samples = tf.tile(tf.reshape(post_means, [NUM_PARAMS, 1]), [1, S])

# Now add the random sample scaled by the covariance
post_samples = tf.add(samples, tf.matmul(post_covariance_chol, eps))


# In calculating the reconstruction cost we need to calculate the log likelihood of the data given a set of model parameters. We do this by observing that any difference between the biexponential model prediction (given these parameters) and the actual noisy data must be a result of the Gaussian noise - hence the likelihood is simply the likelihood of drawing these differences from the Gaussian noise distribution:
# 
# $$\log P(\textbf{y} | A_1; A_2; r_1; r_2; \beta) = \frac{1}{2} \bigg( N \log \beta - \sum{\frac{(y_n - M_n)^2}{\beta}}\bigg)$$
# 
# Here $M_n$ is the model prediction for the nth data point which is calculated by evaluating the biexponential model for the given parameters $A_1$, $A_2$, $r_1$ and $r_2$.

# In[ ]:


# These are our sample of values for the model parameters
a1 = tf.reshape(post_samples[0], [-1, 1])
r1 = tf.exp(tf.reshape(post_samples[1], [-1, 1]))
a2 = tf.reshape(post_samples[2], [-1, 1])
r2 = tf.exp(tf.reshape(post_samples[3], [-1, 1]))

# Get the current estimate of the noise variance remembering that
# we are inferring the log of the noise precision, beta
log_noise_var = -post_samples[4]
noise_var = tf.exp(log_noise_var)

# Each sample value predicts the full set of values in the data sample.
# For our constant-signal model, the prediction is simply a set of 
# constant values. The prediction tensor will have shape [S, N]
# where S is the sample size and N is the number of data values
t = tf.reshape(tf.constant(T, dtype=tf.float32), [1, -1])
prediction = a1*tf.exp(-r1*t) + a2*tf.exp(-r2*t)
diff = tf.reshape(data, [1, -1]) - prediction

# To calculate the likelihood we need the sum of the squared difference between the data  
# and the prediction. This gives a value for each posterior sample so has shape [S]
sum_square_diff = tf.reduce_sum(tf.square(diff), axis=1)

# Now we calculate the likelihood for each posterior sample (shape [S])
# Note that we are ignoring constant factors such as 2*PI here as they 
# are just an fixed offset and do not affect the optimization 
log_likelihood = 0.5 * (-log_noise_var * tf.to_float(N) - sum_square_diff / noise_var)

# Finally to evaluate the expectation value we take the mean across all the posterior
# samples. The negative of this is the reconstruction loss
reconstr_loss = -tf.reduce_mean(log_likelihood)


# For the latent loss we will again use the analytic expression for the K-L divergence of two MVN distributions with a slight modification to the previous code to account for the different number of parameters (5 vs 2)

# In[ ]:


C = post_covariance
C0 = prior_covariance
C0_inv = tf.matrix_inverse(C0)

# m - m0 as row and column vectors
m_minus_m0 = tf.reshape(tf.subtract(post_means, prior_means), [-1, 1])
m_minus_m0_T = tf.reshape(tf.subtract(post_means, prior_means), [1, -1])

term1 = tf.trace(tf.matmul(C0_inv, C))
term2 = -tf.log(tf.matrix_determinant(C) / tf.matrix_determinant(C0))

# Size of the MVN distribution
term3 = -NUM_PARAMS
term4 = tf.matmul(tf.matmul(m_minus_m0_T, C0_inv), m_minus_m0)
          
latent_loss = 0.5 * (term1 + term2 + term3 + term4)

cost = reconstr_loss + latent_loss


# Finally we ask TensorFlow to minimise the total cost iteratively:

# In[ ]:


optimizer = tf.train.AdamOptimizer(learning_rate=0.02)
minimizer = optimizer.minimize(cost)
sess.run(tf.global_variables_initializer())

cost_history = []
for epoch in range(5000):
    sess.run(minimizer)
    cost_history.append(float(sess.run(cost)))
    print("Epoch %i: cost=%f, posterior means=%s" % (epoch+1, sess.run(cost), sess.run(post_means)))


# In[ ]:


final_means = sess.run(post_means)
final_covariance = sess.run(post_covariance)
print("Estimate for amp1: %f (variance: %f)" % (final_means[0], final_covariance[0, 0]))
print("Estimate for amp2: %f (variance: %f)" % (final_means[2], final_covariance[0, 0]))
print("Estimate for r1: %f" % (np.exp(final_means[1]),))
print("Estimate for r2: %f" % (np.exp(final_means[3]),))
print("Estimate for beta (noise): %f" % np.exp(-final_means[4]))


# We can plot the evolution of the total cost and compare the final model prediction against the data and the ground truth signal:

# In[ ]:


plt.figure()
plt.plot(cost_history)
plt.ylim(0, 500)

plt.figure()
plt.plot(DATA_CLEAN, 'g')
plt.plot(DATA, 'rx')
plt.plot(sess.run(prediction[0]), 'b')
plt.show()


# You should get a fairly smooth convergence of the cost and an inferred signal which matches the ground truth fairly closely.
# 
# The biexponential model, despite its simplicity, is quite challenging to infer. The exponential with the higher decay rate only really affects the first few data points and with a small number of samples it is difficult to separate out this contribution from that of a single exponential. You might like to reduce the number of data samples and see at what point the optimization struggles to find the second exponential accurately. This is not really a limitation of the stochastic method - it is simply that we do not have enough information in the data to infer these values accurately.
# 
# Other things you might want to try could include:
# 
#  - Do not infer covariance between the parameters - this should make the inference more robust as we have significantly fewer parameters to estimate
#  - Try inferring the decay rates directly rather than via their log values. It may not end well!
#  - Try modifying the learning rate and sample size to see how this affects the inference
#  - Maybe try implementing mini-batch processing as described in the tutorial (you will need to implement the scaling factor in the reconstruction loss definition)
# 
