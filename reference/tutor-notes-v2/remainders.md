# Remainders

Status: draft. Original material for human review.

For a positive integer divisor d, every integer N has a unique representation
N = dq + r with integer q and remainder r satisfying 0 ≤ r < d. The remainder
is what remains after subtracting a suitable whole multiple of d. The upper
bound matters: a value equal to d can be absorbed into the quotient and is
not a valid final remainder.

If two numbers differ by a multiple of d, they have the same remainder on
division by d. This is often written a ≡ b modulo d. Replacing a large
number by its remainder simplifies arithmetic without changing the remainder
of a sum, difference or product. Reduce the result again if it falls outside
the required interval from zero through d − 1.

If a leaves remainder r and b leaves remainder s, the remainder of a + b is
the remainder of r + s. The product rule similarly reduces ab to rs before
taking the final remainder. These rules follow by expanding a = dq + r and
b = dt + s: every discarded term contains a factor d. Arbitrary division is
not covered by the same rule.

For example, 47 divided by 6 is 7 with remainder 5 because 47 = 6 × 7 + 5.
The remainder of 47 + 20 modulo 6 can be found from 5 + 2 = 7, which reduces
to 1. Directly, 67 = 6 × 11 + 1. The remainder of 47 × 20 reduces from
5 × 2 = 10 to 4, agreeing with 940 = 6 × 156 + 4.

For a negative result, add enough multiples of the positive divisor to reach
the required nonnegative interval. For instance, −1 = 6 × (−1) + 5, so its
remainder modulo 6 is 5 under this convention. Stating the convention avoids
confusion with programming languages that define a signed remainder differently.

Common mistakes are stopping at a value at least the divisor, confusing the
quotient with the remainder, and applying a product rule to division without
justification. Always check both N = dq + r and 0 ≤ r < d. These notes do
not cover simultaneous congruences, modular inverses, or general theorems for
huge powers; use a separate method when those are needed.
