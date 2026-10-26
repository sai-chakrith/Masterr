# Primes and factors

Status: draft. Original material for human review.

A positive factor of a positive integer N divides N without a remainder.
A prime is an integer greater than one with exactly two positive factors,
one and itself. A composite integer is greater than one and has more than two
positive factors. One is neither prime nor composite. Two is prime and is the
only even prime; every larger even integer has the additional factor two.

To test whether N greater than one is prime, look for a divisor between two
and the square root of N, inclusive. If N = ab with a and b both greater than
one, at least one of them is at most the square root. Otherwise their product
would exceed N. This explains why checking larger potential divisors adds no
new evidence once every smaller one has been excluded.

To enumerate factors, try positive candidate divisors d up to the square root.
Whenever d divides N, record both d and N/d. If d = N/d, record that value
only once. Factor pairs account for every divisor; a perfect square has one
pair whose two entries coincide. Thus a positive perfect square has an odd
number of positive factors.

Prime factorisation writes N as a product of powers of distinct primes. If
N = p^a × q^b for different primes p and q, the number of positive factors is
(a + 1)(b + 1). A factor chooses a power from zero through a and independently
a power from zero through b. The same reasoning extends to more prime factors.

For example, 36 = 2^2 × 3^2. Its positive factors number (2 + 1)(2 + 1) = 9.
Listing confirms them: 1, 2, 3, 4, 6, 9, 12, 18 and 36. The pairs are 1×36,
2×18, 3×12, 4×9 and 6×6. Counting the final pair twice would incorrectly
give ten factors instead of nine.

Common mistakes are calling one prime, forgetting to test a square-root
divisor, and confusing distinct prime factors with all positive factors.
Thirty-six has two distinct prime factors, 2 and 3, but nine positive factors.
Read what the question asks before choosing a counting method. These notes
do not cover negative-factor counts, prime probability estimates, or advanced
factorisation algorithms.
