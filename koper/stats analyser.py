import numpy as np
from scipy.stats import norm

# Given parameters
mu =20.76   #49.98                  
sigma = 17.47     #19.79
total_area = 5

# Precompute constants
z0 = (0 - mu) / sigma
z100 = (100 - mu) / sigma

Phi_z0 = norm.cdf(z0)
Phi_z100 = norm.cdf(z100)
D = Phi_z100 - Phi_z0

def x_from_y(y):
    """
    Returns x such that integral from x to 100 equals y
    """
    if y < 0 or y > total_area:
        raise ValueError("y must be between 0 and 5")

    Phi_zx = Phi_z0 + (total_area - y) / total_area * D
    z_x = norm.ppf(Phi_zx)
    x = mu + sigma * z_x
    return x

# Example

print(x_from_y(0.75))
