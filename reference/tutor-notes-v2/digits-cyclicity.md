# Place value and units-digit cycles

Status: draft. Original material for human review.

Decimal notation uses powers of ten. A three-digit number with digits a, b
and c has value 100a + 10b + c. Its leading digit a is from one through nine;
the other digits may be zero. A digit is not the same as its place-value
contribution: the digit 4 contributes 400 in 427 but 4 in 724.

Reversing digits changes their place values. A two-digit number 10a + b
becomes 10b + a when reversed, possibly losing a leading zero. Their
difference is 9(a − b). Expressing the two numbers algebraically avoids
guessing and makes any digit restrictions visible. A solution must satisfy
those restrictions as well as the algebraic equation.

The units digit of an integer is its remainder modulo ten for nonnegative
integers. To find the units digit of a sum or product, use only the units
digits of its terms, then reduce the result to a single digit. Higher-place
contributions are multiples of ten and cannot affect this last digit.

Repeated powers can produce a repeating cycle of units digits. For powers
of 7 with positive exponents, the first four units digits are 7, 9, 3 and 1.
Multiplying the last digit by 7 returns to 7, so the cycle repeats every
four powers. Match the exponent to the cycle position; a zero remainder
means the final position of the cycle, not an extra position before it.

For example, 23 divided by 4 leaves remainder 3, so 7^23 has the third
units digit in that cycle, namely 3. The starting terms are 7^1 = 7,
7^2 = 49, 7^3 = 343 and 7^4 = 2401. These explicitly confirm the order of
the four positions. An exponent of zero is a separate case: 7^0 = 1.

Common mistakes are using the exponent itself as the units digit, starting
the cycle at exponent zero while using a one-based position rule, and
allowing a leading zero in a number specified as having a fixed number of
digits. Check the cycle using small powers before applying it to a large
exponent. These notes cover ordinary decimal place value and units digits,
not the last two digits, negative exponents, or non-decimal number bases.
