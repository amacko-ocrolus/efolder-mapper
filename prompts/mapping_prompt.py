"""Shared prompt template used by all three AI services."""


# Context explaining Ocrolus's non-obvious form type naming conventions.
# This is injected into every prompt so AI services can correctly identify
# what a document is before attempting to map it to a container.
OCROLUS_NAMING_GUIDE = """
**Ocrolus Form Type Naming Conventions (read this before mapping):**

Ocrolus uses several non-obvious naming patterns. Understanding them is critical to
choosing the right lender container.

1. `A_` PREFIX — "Annotated" IRS/government forms
   Form types starting with `A_` are Ocrolus's annotated extractions of IRS or other
   government tax forms. The number after `A_` is the IRS form number.
   Examples:
   - `A_1040` or `A_1040_2022` = Annotated IRS Form 1040 (U.S. Individual Income Tax Return)
   - `A_1040_NR` = Annotated IRS Form 1040-NR (Nonresident Alien Income Tax Return)
   - `A_1040_SS` = Annotated IRS Form 1040-SS (U.S. Self-Employment Tax Return)
   - `A_1041` = Annotated IRS Form 1041 (U.S. Estate or Trust Income Tax Return)
   - `A_1065` or `A_1065_2022` = Annotated IRS Form 1065 (U.S. Partnership Return of Income)
   - `A_1120` or `A_1120_2022` = Annotated IRS Form 1120 (U.S. Corporation Income Tax Return)
   - `A_1120S` or `A_1120S_2022` = Annotated IRS Form 1120-S (S-Corporation Tax Return)
   - `A_1098` = Annotated IRS Form 1098 (Mortgage Interest Statement)
   - `A_1098_E` = Annotated IRS Form 1098-E (Student Loan Interest Statement)
   - `A_1098_T` = Annotated IRS Form 1098-T (Tuition Statement)
   - `A_1099_*` = Annotated IRS Form 1099 variants (various income/payment reporting)
   - `A_1099_INT` = Interest income; `A_1099_DIV` = Dividends; `A_1099_R` = Retirement distributions
   - `A_1099_MISC` / `A_1099_NEC` = Miscellaneous / Non-employee compensation
   - `A_1099_G` = Government payments (unemployment, tax refunds)
   - `A_1099_S` = Proceeds from real estate transactions
   - `A_4506` / `A_4506_C` / `A_4506_T` = Annotated IRS Form 4506 (Request for Tax Transcript)
   - `A_4562` = Annotated IRS Form 4562 (Depreciation and Amortization)
   - `A_4797` = Annotated IRS Form 4797 (Sales of Business Property)
   - `A_4835` = Annotated IRS Form 4835 (Farm Rental Income and Expenses)
   - `A_8825` = Annotated IRS Form 8825 (Rental Real Estate Income and Expenses of a Partnership/S-Corp)
   - `A_8949` = Annotated IRS Form 8949 (Sales and Other Dispositions of Capital Assets)
   - `A_6252` = Annotated IRS Form 6252 (Installment Sale Income)
   - `A_3903` = Annotated IRS Form 3903 (Moving Expenses)
   - `A_1096` = Annotated IRS Form 1096 (Annual Summary and Transmittal of U.S. Information Returns)
   - `A_1125_A` = Annotated IRS Form 1125-A (Cost of Goods Sold)
   - `A_1128` = Annotated IRS Form 1128 (Application to Adopt, Change, or Retain a Tax Year)
   - `A_1310` = Annotated IRS Form 1310 (Statement of Person Claiming Refund Due a Deceased Taxpayer)
   Less common IRS forms that still appear:
   - `A_1000` = Annotated IRS Form 1000 (Ownership Certificate)
   - `A_1023` = Annotated IRS Form 1023 (Application for Tax-Exempt Status — nonprofit)
   - `A_1024` = Annotated IRS Form 1024 (Application for Recognition of Exemption)
   - `A_1042` = Annotated IRS Form 1042 (Annual Withholding Tax Return for U.S. Source Income of Foreign Persons)
   - `A_1094_B` / `A_1094_C` = Annotated IRS Form 1094-B/C (ACA health coverage transmittal)
   - `A_1095_A` / `A_1095_B` / `A_1095_C` = Annotated IRS Form 1095 variants (ACA health insurance coverage)
   - `A_1116` = Annotated IRS Form 1116 (Foreign Tax Credit)
   - `A_1117` / `A_1118` = Annotated IRS Forms 1117/1118 (Foreign tax-related)
   - `A_2210` = Annotated IRS Form 2210 (Underpayment of Estimated Tax)
   For any `A_XXXX` form where the IRS form number is not immediately recognizable,
   treat it as a tax-related financial document and map it to the most appropriate
   tax, income, or financial documentation container.

2. BARE FANNIE MAE / FREDDIE MAC FORM NUMBERS
   Some form types are just numbers — these are standard GSE industry form numbers:
   - `1003` / `1003_2009` / `1003_2020` = Uniform Residential Loan Application (URLA) — the primary mortgage application
   - `1005` = Verification of Employment (VOE)
   - `1008` / `1008_2009` / `1008_2018` = Uniform Underwriting and Transmittal Summary
   - `1032` = Appraisal Update and/or Completion Certificate

3. SHORT IRS / GOVERNMENT FORM CODES
   - `W2` = IRS Form W-2 (Wage and Tax Statement from employer)
   - `W3` = IRS Form W-3 (Transmittal of Wage and Tax Statements)
   - `W9` = IRS Form W-9 (Request for Taxpayer Identification Number)
   - `H1B` = H-1B Visa petition/approval notice (used to verify foreign worker employment status)

4. SCHEDULE SUFFIXES
   Form types containing `_SCHEDULE_A`, `_SCHEDULE_B`, `_SCHEDULE_C`, etc. are specific
   IRS schedules attached to the parent form. For example:
   - `A_1040_SCHEDULE_A` = Schedule A (Itemized Deductions) attached to Form 1040
   - `A_1040_SCHEDULE_C` = Schedule C (Profit or Loss from Business) attached to Form 1040
   - `A_1040_SCHEDULE_D` = Schedule D (Capital Gains and Losses) attached to Form 1040
   - `A_1040_SCHEDULE_E` = Schedule E (Supplemental Income and Loss — rental, partnership, S-corp)
   - `A_1065_SCHEDULE_K_1` = Schedule K-1 (Partner's Share of Income) from Form 1065

5. YEAR SUFFIXES
   `_2018`, `_2019`, `_2020`, etc. at the end of a form name indicate the tax year of the form.
   These are the same document type regardless of year and should map to the same container.

6. WORKSHEET AND CALCULATION FORMS
   Form types ending in `_WORKSHEET`, `_CALCULATION`, `_RECONCILIATION`, or `_ANALYSIS`
   are calculation support documents produced by tax preparation software alongside the
   primary tax return. They belong in the same container as the parent tax form.
"""


def build_mapping_prompt(
    ocrolus_types: list[str],
    lender_containers: list[str],
) -> str:
    """Build the bulk mapping prompt sent to each AI service.

    Each service must return a JSON object where every Ocrolus form type maps to
    an object with a best-guess container and a confidence score (0.0–1.0).
    NO_MATCH is disallowed — services must always pick the closest available container.
    """
    ocrolus_list = "\n".join(f"  - {t}" for t in ocrolus_types)
    container_list = "\n".join(f"  - {c}" for c in lender_containers)

    return f"""You are an experienced mortgage loan operations professional and ICE Encompass administrator. You understand the full mortgage origination workflow — from application through underwriting, closing, and post-closing — and how loan documents are organized in an Encompass eFolder. Your task is to map Ocrolus document form types to the lender's document container names exactly as an experienced Encompass admin would file them.
{OCROLUS_NAMING_GUIDE}
**Ocrolus Document Form Types to Map:**
{ocrolus_list}

**Lender Encompass Document Container Names:**
{container_list}

**Instructions:**
1. For each Ocrolus form type listed above, use the naming conventions guide above to first understand what the document actually is, then select the single best-matching lender document container name from the list above.
2. Base your matching on semantic similarity — the container that would most logically hold that type of document in a mortgage workflow.
3. **CRITICAL — Disclosures must go to disclosure containers, not subject-matter containers:**
   Any form type that is a Disclosure (contains the word "DISCLOSURE", "NOTICE", or "ACKNOWLEDGMENT/ACKNOWLEDGEMENT" in its name) must be mapped to a disclosure-specific container — never to a production or subject-matter container. The subject of the disclosure is irrelevant to where it is filed.
   Examples of correct disclosure mapping logic:
   - "APPRAISAL_FEE_DISCLOSURE" → a Disclosure container (NOT an Appraisal container)
   - "AFFILIATED_BUSINESS_ARRANGEMENT_DISCLOSURE" → a Disclosure container (NOT a Business/Legal container)
   - "ARM_DISCLOSURE" → a Disclosure container (NOT a Loan Terms container)
   - "HOMEOWNERSHIP_COUNSELING_NOTICE" → a Disclosure/Notice container (NOT a Counseling container)
   - "ACKNOWLEDGMENT_OF_RECEIPT_OF_LOAN_ESTIMATE" → a Disclosure container (NOT a Loan Estimate container)
   When in doubt: if the document is something the lender gives the borrower to sign or acknowledge for legal/regulatory compliance purposes, it belongs in a disclosure container.
4. Always provide a best-guess — never omit a form type or leave its container blank. Even if no container is a strong match, pick the closest option.
5. For each mapping, provide a confidence score from 0.0 (very uncertain) to 1.0 (very confident). If you are uncertain what the form type is even after consulting the naming guide, use a lower confidence score.
6. Return ONLY a valid JSON object. Each key is an Ocrolus form type (exactly as written above) and each value is an object with:
   - "container": the best-matching lender container name (must be exactly from the list above)
   - "confidence": a float from 0.0 to 1.0 representing your confidence in the match
7. Do not add any explanation, commentary, or markdown formatting. Return raw JSON only.

Example output format:
{{
  "A_1040_2022": {{"container": "Tax Returns", "confidence": 0.95}},
  "W2": {{"container": "Tax Returns", "confidence": 0.98}},
  "1003_2020": {{"container": "Loan Application", "confidence": 0.99}},
  "A_1042": {{"container": "Tax Returns", "confidence": 0.55}}
}}

Return the complete JSON mapping now:"""
