# Integers and properties

Status: draft. Original material for human review.

Integers are the whole numbers together with their negatives and zero. Examples
are −3, 0 and 7; 1/2 is not an integer. A positive integer is greater than zero,
and a negative integer is less than zero. Zero is neither positive nor negative.
On a number line the value increases to the right, so −2 is greater than −5.

An integer is even if it equals 2k for some integer k. An odd integer equals
2k + 1 for some integer k. These definitions include negative values: −6 is
even and −5 is odd. Zero is even because it equals 2 × 0. Divisibility here
means exact integer division with remainder zero, not a rounded quotient.

Adding two even integers gives 2a + 2b = 2(a + b), which is even. Adding two odd
integers gives (2a + 1) + (2b + 1) = 2(a + b + 1), also even. An even plus an
odd integer is odd. A product with an even factor is even; a product of two odd
integers is odd. These forms explain the rules rather than merely listing them.

To count even integers in an inclusive interval from L to U, find the first
even value E at least L and the last even value F at most U. If E exceeds F,
the count is zero. Otherwise the values are E, E + 2, and so on through F,
so their count is (F − E)/2 + 1. The added one includes the starting term.

For example, the even integers from −2 through 8 are −2, 0, 2, 4, 6 and 8.
Their count is (8 − (−2))/2 + 1 = 10/2 + 1 = 6. Both endpoints are included.
From 3 through 3 there are no even integers because the first eligible even
value would be 4, beyond the upper endpoint.

Common mistakes are excluding zero, treating a negative even number as odd,
and counting gaps instead of terms. First check whether the interval includes
its endpoints, then apply the spacing rule. Small examples are useful checks,
but one successful example cannot prove a claim about every integer. The
algebraic forms 2k and 2k + 1 give a general explanation.

These notes cover integer order, parity and counting equally spaced even
values. They do not establish rules for prime factorisation, general sequences
or rational-number denominators. Those methods need their own topic notes.
