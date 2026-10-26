# Guide and research: U.S. taxes (federal, state and local)

This guide summarizes the research behind DeclaraFácil USA: how federal, state and county/city income taxes are calculated for tax years 2025 and 2026, how TurboTax works, what the IRS app (Direct File) offered, and how this application replicates that flow.

## 1. Calendar

- Tax year 2025: the return is due April 15, 2026 (automatic extension with Form 4868 to October 15, 2026; the extension is to file, not to pay).
- Tax year 2026: due April 15, 2027.
- 2026 estimated payments (self-employed): April 15, 2026, June 15, 2026, September 15, 2026 and January 15, 2027.
- Common state exceptions: Virginia May 1, Delaware and Iowa April 30, Louisiana May 15, Hawaii April 20.

## 2. Federal income tax (Form 1040)

### 2.1 How the calculation flows

1. Total income = wages (W-2) + interest + dividends + taxable retirement income + taxable Social Security + capital gains + self-employment (Schedule C) + unemployment + other.
2. Minus adjustments (Schedule 1): half of self-employment tax, HSA, IRA, student loan interest, educator expenses, self-employed health insurance = Adjusted Gross Income (AGI).
3. Minus the standard or itemized deduction (Schedule A), the QBI deduction (section 199A) and the new Schedule 1-A deductions = taxable income.
4. Tax from the brackets (long-term gains and qualified dividends use 0%, 15% or 20%).
5. Plus AMT (if any). Minus nonrefundable credits (child, dependent care, education, saver's).
6. Plus other taxes (self-employment 15.3%, additional Medicare 0.9%, net investment income tax 3.8%).
7. Minus payments (withholding, estimated) and refundable credits (EITC, ACTC, 40% of AOTC) = refund or amount owed.

### 2.2 OBBBA (One Big Beautiful Bill Act, P.L. 119-21, signed July 4, 2025)

- Makes the 7 brackets (10% to 37%) and the larger standard deduction permanent.
- 2025 standard deduction: $15,750 single/married filing separately, $31,500 married filing jointly, $23,625 head of household. 2026: $16,100 / $32,200 / $24,150.
- Child tax credit: $2,200 per child under 17 (2025 and 2026); refundable portion up to $1,700; requires an SSN.
- New Schedule 1-A (2025-2028): qualified tips up to $25,000; overtime (premium only) up to $12,500 ($25,000 joint); both reduced when MAGI exceeds $150,000 ($300,000 joint). Interest on a loan for a new U.S.-assembled car up to $10,000 (reduced above $100,000 / $200,000 MAGI). Additional $6,000 deduction per person 65+ (reduced by 6% of MAGI above $75,000 / $150,000).
- SALT cap (state and local taxes): $40,000 in 2025 and $40,400 in 2026, reduced by 30% of MAGI above $500,000 ($505,000 in 2026), never below $10,000.
- From 2026: cash charitable deduction for non-itemizers ($1,000 / $2,000), 0.5%-of-AGI floor for itemized charitable gifts, and a cap on the benefit of itemized deductions for the 37% bracket.
- Child and dependent care credit from 2026: 50% maximum rate (phasing down to 35% and then to 20% based on AGI).
- 2026 AMT: exemption $90,100 / $140,200; phase-out from $500,000 / $1,000,000 at 50%.

### 2.3 Federal brackets

| Rate | Single 2025 | Married joint 2025 | Single 2026 | Married joint 2026 |
|------|------|------|------|------|
| 10% | $0 | $0 | $0 | $0 |
| 12% | $11,925 | $23,850 | $12,400 | $24,800 |
| 22% | $48,475 | $96,950 | $50,400 | $100,800 |
| 24% | $103,350 | $206,700 | $105,700 | $211,400 |
| 32% | $197,300 | $394,600 | $201,775 | $403,550 |
| 35% | $250,525 | $501,050 | $256,225 | $512,450 |
| 37% | $626,350 | $751,600 | $640,600 | $768,700 |

Head of household and married filing separately have their own tables (included in data/federal_YYYY.json).

### 2.4 Other key values

- Maximum EITC: $8,046 (2025) and $8,231 (2026) with 3+ children; investment income limit $11,950 / $12,200.
- Social Security wage base: $176,100 (2025) and $184,500 (2026).
- Student loan interest: maximum $2,500.
- Educators: $300 (2025), $350 (2026).
- 2026 saver's credit AGI limits: $80,500 (joint), $60,375 (head of household), $40,250 (others).
- IRS Direct File: NOT available in the 2026 filing season. Free alternatives: IRS Free File (IRS partner software for lower AGI), VITA/TCE and Free File Fillable Forms.

## 3. State income taxes

- 8 states do not tax wages: Alaska, Florida, Nevada, New Hampshire (repealed its interest/dividends tax in 2025), South Dakota, Tennessee, Texas and Wyoming. Washington taxes only long-term capital gains (7%, and 9% above $1 million).
- 15 states have a flat tax in 2026 (AZ 2.5%, CO 4.4%, GA 5.19%, ID 5.3%, IL 4.95%, IN 2.95%, IA 3.8%, KY 3.5%, LA 3%, MI 4.25%, MS 4%, NC 3.99%, OH 2.75%, PA 3.07%, UT 4.5%).
- The rest (plus DC) use graduated brackets; the highest rate is California's 13.3% (including the 1% mental health tax above $1M).
- Almost all start from federal AGI; Colorado, Idaho, Iowa, Montana, New Mexico, North Dakota and South Carolina start from federal taxable income.
- Most exempt Social Security; CO, CT, MN, MT, NM, RI, UT and VT tax it fully or partially.
- Several states had not adopted the OBBBA standard deduction in early 2026 (e.g., AZ, ME, SC): check the state instructions.
- 2026 changes: rate cuts in IN, KY, MS, MT, NE, NC, OH (moves to a flat tax) and OK (3 brackets). Retroactive 2025 changes: GA 5.19%, ID 5.3%, UT 4.5%, MD new 6.25% and 6.5% brackets with a flat standard deduction ($3,350 / $6,700) and a 2% capital gains surtax when AGI > $350,000.
- Ohio (ORC 5747.02): 2025 = $342 + 2.75% over $26,050 and $2,394.32 + 3.125% over $100,000; 2026 = $332 + 2.75% over $26,050.

## 4. Local income taxes (counties and cities)

- Maryland: all 23 counties and Baltimore City levy 2.25% to 3.30% on MD taxable income (Anne Arundel and Frederick use bracketed rates). For 2026 Allegany rises to 3.20% and Kent to 3.30%.
- Indiana: all 92 counties levy between 0.5% and 3.0% (e.g., Marion 2.02%). In 2026 Carroll, Grant, Greene, Howard, Shelby and Union increase.
- New York City: 3.078% to 3.876% of NY taxable income. Yonkers: 16.75% of state tax.
- Pennsylvania: Philadelphia (resident Wage Tax 3.74% from July 2025, 3.735% from July 2026); almost every municipality levies an EIT (~1%; Pittsburgh 3%).
- Ohio, Michigan, Kentucky, Missouri (Kansas City and St. Louis 1%), Alabama, Delaware (Wilmington), Iowa (school surtax), Oregon (Portland Metro and Multnomah on high incomes) and Colorado (Denver and Aurora monthly occupational taxes).
- Elsewhere counties have no income tax; they do levy property taxes (deductible on Schedule A within the SALT cap) and sales taxes (national average combined rate 7.53% in 2026).

## 5. How TurboTax works (and what this app replicates)

1. Profile and import: personal information, filing status, dependents; imports last year's return and W-2/1099 forms.
2. Guided interview: plain-language questions by section (income, deductions and credits, other taxes), while a refund meter updates live at the top.
3. Automatic comparison of the standard vs. itemized deduction.
4. State return: prepared after the federal one, reusing the data.
5. Review ("CompleteCheck"): looks for errors, missing fields and unusual amounts.
6. Federal and state e-file, payment or refund deposit.

DeclaraFácil USA replicates steps 1 to 5 (main menu, sectioned interview with a sidebar, live federal/state/local refund meter, review with findings, and export of the 1040 + state + local draft to PDF/HTML). It does not e-file: transmitting to the IRS requires being an authorized provider (EFIN and MeF testing).

## 6. The IRS app

- IRS Direct File (2024-2025): let taxpayers in participating states file for free directly with the IRS, with a simple interview for W-2s, Social Security, unemployment, interest, EITC and CTC. It was discontinued and will not be available in 2026.
- IRS2Go (mobile app) and the IRS Online Account: check refunds, pay (Direct Pay), view transcripts.
- This app borrows Direct File's short plain-language interview and its line-by-line result view.

## 7. Estimator limitations

Not modeled: business depreciation and property, rentals (Schedule E), K-1s, underpayment penalties (Form 2210), the 10% early-withdrawal penalty, energy credits, unrecaptured gain (25%/28%) rates, detailed part-year resident rules, NY and CT bracket recapture, and state-specific credits (add them as "other state credits"). Rates live in data/*.json and can be edited.

## Sources

- IRS, Rev. Proc. 2025-32 and IR-2025-103 (2026 adjustments with OBBBA): irs.gov/newsroom
- IRS, OBBBA fact sheet (tips, overtime, car loan, seniors) and Schedule 1-A
- IRS, Rev. Proc. 2024-40 (2025 adjustments); 2026 retirement limits (Notice 2025-67)
- Tax Foundation: State Individual Income Tax Rates and Brackets 2025 and 2026; State and Local Sales Tax Rates 2026
- Comptroller of Maryland: Withholding Tax Facts 2025 and 2025 legislative session Tax Alert
- Indiana Department of Revenue: 2025 county rates and 2026 changes
- City of Philadelphia (Wage Tax); Ohio Revised Code 5747.02
- Reporting on the end of IRS Direct File (Kiplinger, NATP, press)
