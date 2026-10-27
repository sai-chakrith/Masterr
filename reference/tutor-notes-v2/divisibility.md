# Divisibility

Status: draft. Original material for human review.

An integer N is divisible by a nonzero integer d when N = dq for an integer q.
Equivalently, division by d leaves remainder zero. Divisibility tests are ways
to decide this without performing the whole division. Apply a test to the
specified divisor; satisfying a rule for one divisor does not settle another.

In decimal notation a number is divisible by 2 when its last digit is even,
and by 5 when its last digit is 0 or 5. It is divisible by 10 when its last
digit is 0. These tests follow because all earlier place-value contributions
are multiples of 10. A last digit by itself does not decide divisibility by 3.

A number is divisible by 3 when its digit sum is divisible by 3. The same rule
holds for 9 with divisor 9. Each power of 10 leaves remainder 1 under either
divisor, so the number and its digit sum have the same remainder. A digit sum
of 12 proves divisibility by 3 but not by 9.

Divisibility by 6 requires divisibility by both 2 and 3. The factors are
coprime, so both conditions together suffice. For 4, inspect the last two
digits; for 8, inspect the last three digits. All earlier places contribute
multiples of 100 or 1000 respectively, and those are divisible by 4 or 8.

For example, find the digit x in 53x that makes the number divisible by 6.
The final digit must be even, so x is one of 0, 2, 4, 6 and 8. The digit sum
is 8 + x. These choices give 8, 10, 12, 14 and 16. Only 12 is divisible by 3,
so x = 4. Check the completed number: 534 = 6 × 89.

When combining tests, write every required condition before trying digits.
Checking only the digit sum for divisibility by 6 misses the evenness condition.
Also, being divisible by 2 and 4 does not imply divisibility by 8: 12 satisfies
the first two conditions but not the third. Multiplying divisors is justified
by the coprime-factor rule, not by an unrestricted general rule.

## More tests and combined conditions

For 11, subtract the sum of digits in alternating positions from the other
sum. The number is divisible by 11 exactly when this difference is a multiple
of 11, including zero. This follows from 10 having remainder -1 modulo 11.
For 3x52 the difference is (3 + 5) - (x + 2) = 6 - x, so x = 6.
For 12 use 3 and 4; for 36 use 4 and 9; for 44 use 4 and 11.
Try digits 0 through 9 and keep every digit satisfying all the conditions;
only claim a unique answer when exactly one remains.

## Counting multiples

Among integers 1 through N there are floor(N/d) multiples of positive d,
where floor means round down. Between positive L and U inclusive there are
floor(U/d) - floor((L-1)/d). For example multiples of 6 from 100 through
300 number 50 - 16 = 34. For two divisors a and b, common multiples are
multiples of lcm(a,b), found using prime factors with their maximum powers.
Thus multiples of both 6 and 8 through 500 number floor(500/24) = 20.

For a or b, add their counts and subtract the common count once. For exactly
one, subtract the common count twice. Through 100, multiples of 2 or 3 number
50 + 33 - 16 = 67. For neither, subtract the union count from the total.
For three divisors add singles, subtract all three pairwise lcm counts, then
add the triple lcm count. Through 300, multiples of 3, 5 or 7 number
100 + 60 + 42 - 20 - 14 - 8 + 2 = 162.
To count numbers coprime to m, exclude multiples of each distinct prime
factor of m with the same inclusion-exclusion rule. Count each prime once.

## Related sums and products

The positive multiples of d through N sum to d*k*(k+1)/2, with k=floor(N/d).
Multiples of 5 through 100 sum to 5*20*21/2 = 1050. A digit sum divisible by
9 is equivalent to the number being divisible by 9; use interval counting
for two-digit or three-digit restrictions. Three-digit multiples of 11
number floor(999/11)-floor(99/11)=90-9=81.

A product of three consecutive integers always contains a multiple of 3
and an even integer, so it is divisible by 6. It need not be divisible by
a larger fixed integer: 1*2*3=6. A factorial's trailing zeros count factors
of 10, each made from 2 and 5. There are more factors of 2, so count factors
of 5: floor(n/5)+floor(n/25)+floor(n/125)+... until the terms are zero.
For 25!, there are 5+1=6 trailing zeros. Do not confuse a count, a sum,
a missing digit, and a remainder: first identify what the question requests.
