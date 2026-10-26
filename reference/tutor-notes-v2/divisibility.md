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

These notes cover common decimal tests and simple missing-digit problems.
They do not provide every possible divisibility test, the divisibility rule
for 11, or a general algorithm for several unknown digits. If a question
requires those methods, the notes do not cover them.
