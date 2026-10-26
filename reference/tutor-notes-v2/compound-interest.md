# Compound interest

Status: draft. Original material for human review.

Compound interest adds earned interest to the balance before the next
interest period. With starting principal P, rate r percent per period,
and n whole periods, the final amount is A = P(1 + r/100)^n. Compound
interest is A − P. The exponent counts compounding periods, not simply
calendar years regardless of how often interest is added.

The formula follows from repeated multiplication. After one period the
balance is P(1 + r/100). Applying the same percentage to that new
balance multiplies it by the same factor again. After n periods there
are n factors. Simple interest uses only the original principal, so its
linear formula cannot replace this repeated multiplication.

If a nominal annual rate r is explicitly compounded m times per year,
the periodic rate is r/m percent and the number of periods over t years
is mt, where the problem supplies a compatible duration. The amount is
P(1 + r/(100m))^(mt). This convention is different from an effective
annual rate; use it only when the rate is stated as nominal with that
compounding frequency.

For example, 1,000 rupees at 10% annually compounded for two years grows
to 1,000 × 1.10^2 = 1,210 rupees. Interest is 210 rupees. The first
year earns 100 rupees; the second earns 110 on the new balance of 1,100.
Simple interest over the same two years would be 200, so the extra ten
rupees is interest earned on the first year's interest.

For differing period rates, multiply the separate factors rather than
using one rate raised to a power. A decrease or depreciation uses a
factor 1 − r/100 under the stated repeated-percentage assumption. Do
not round each intermediate balance unless the question explicitly
requires a rounding convention; otherwise keep sufficient precision
until the final amount.

Common mistakes are giving the amount instead of the interest, dividing
the rate for half-yearly compounding without doubling the period count,
and treating a nominal rate as an effective annual rate. These notes
cover repeated fixed-period percentage changes, not instalment loans,
irregular cash flows, fees, taxes, or fractional-period contract rules.
