# HCF and LCM

Status: draft. Original material for human review.

The highest common factor, HCF, of positive integers is the largest positive
integer dividing all of them. It is also called the greatest common divisor.
The least common multiple, LCM, is the smallest positive integer divisible by
all of them. A factor divides a number; a multiple is divided by that number.
Keeping those directions distinct helps identify which quantity a question needs.

Prime factorisation provides a systematic method. For the HCF take every prime
that occurs in all the numbers and use its smallest exponent. For the LCM take
every prime that occurs in any number and use its largest exponent. A common
factor cannot require more copies of a prime than one input contains. A common
multiple must contain enough copies to accommodate every input.

For two positive integers a and b, HCF(a,b) × LCM(a,b) = ab. This follows
because, for each prime, the smaller exponent plus the larger exponent equals
the sum of the two input exponents. Consequently LCM(a,b) = ab/HCF(a,b).
The product identity is a two-number rule; do not apply it unchanged to three
or more numbers.

For example, 12 = 2^2 × 3 and 18 = 2 × 3^2. Their HCF is 2 × 3 = 6.
Their LCM is 2^2 × 3^2 = 36. Check that both 12 and 18 divide 36, and both
are divisible by 6. The product check gives 6 × 36 = 216 and 12 × 18 = 216.
These checks support both computed values.

An HCF question may ask for the greatest equal length that cuts several
lengths without waste. An LCM question may ask when repeating events next
occur together, assuming they start together and have fixed integer periods.
Translate the wording into divisibility before calculating. Put all measured
lengths or periods into the same units first.

Common mistakes are interchanging the largest and smallest exponents, using
the sum instead of the product identity, and treating every scheduling question
as an LCM problem without checking the start times. HCF cannot exceed the
smallest positive input, and LCM cannot be smaller than the largest input.
These bounds help catch reversed answers. These notes do not cover nonzero
starting offsets or non-integer measurement uncertainty.
