# Real documents for the synthetic finance model

Checked and downloaded on 14 October 2026. Six original PDFs are in [finance-real](demo-inputs/finance-real/).
All files came from official publisher URLs. The [manifest](demo-inputs/finance-real/manifest.json) records checksums, sizes, page counts, and isolated import results.
The HSBC guide is now uploaded to the local Supporting materials library, revision 1, with 13 extracted sections.
The two previous synthetic finance uploads were removed after confirming they had no links or model usage.
No model attachments, approvals, or publications were changed. See the [replacement record](demo-inputs/finance-real/local-staging.json).

**Start with the HSBC guide.** Its illustrated payment form has the closest field-level correspondence to the fixture.
The documents explain real payment concepts. They do not establish that any synthetic customer used these banks or services.

Page numbers below are physical PDF positions, starting at 1.

## Downloaded collection

| File | Publisher source | Pages to inspect | Why it matches |
| --- | --- | --- | --- |
| [HSBC Smartform guide](demo-inputs/finance-real/hsbc-smartform-completion-guide.pdf), 12 pages | [HSBC original](https://www.hsbc.com.sg/content/dam/hsbc/sg/documents/forms/smartform-step-by-step-guide.pdf) | 4: illustrated form; 5: account/currency/amount; 7: beneficiary; 8: FX | Sender account, recipient account, amount basis, payment currency, and exchange-rate context |
| [DBS remittance FAQ](demo-inputs/finance-real/dbs-remittance-online-faq.pdf), 3 pages | [DBS original](https://www.dbs.com.sg/sme/pdf/faq-remittanceonline.pdf) | 3: questions 22–23 | Tables distinguish transfer methods, timing, and supported currencies |
| [ABS FAST FAQ, July 2026](demo-inputs/finance-real/abs-fast-faq-2026-07-23.pdf), 4 pages | [ABS original](https://abs.org.sg/docs/library/fast-faq---23-jul-2026.pdf) | 1: scope; 2: payment comparison and value-date caveat | SGD payment-channel context; receipt timing differs from value date |
| [ABS FAST fact sheet, July 2026](demo-inputs/finance-real/abs-fast-fact-sheet-2026-07-07.pdf), 8 pages | [ABS original](https://abs.org.sg/docs/library/2026-07-07-fast-fact-sheet.pdf) | 1: comparison table | Payment types and receipt timing; later pages describe participating institutions and account formats |
| [ABS Making Sense of GIRO, September 2009](demo-inputs/finance-real/abs-making-sense-of-giro-2009.pdf), 6 pages | [ABS original](https://www.abs.org.sg/docs/library/makingsensegiro_sept09.pdf) | 1: payment roles; 2: reconciliation and failed deductions | Historical payment-authorisation and unsuccessful-payment context |
| [BIS cross-border payments survey](demo-inputs/finance-real/bis-cross-border-payments-survey-2024.pdf), 26 pages | [BIS original](https://www.bis.org/publications/cpmi-brief-10-moving-results-2024-cross-border-payments-monitoring-survey.pdf) | 5: Graph 2 | Real stacked charts show system types, processed currencies, and currency arrangements |

The BIS document was published in December 2025 and describes the 2024 survey.
The GIRO document is historical; its fees and schedules must not become current model rules.
Publication dates were not established for the HSBC and DBS guides. Preserve their downloaded revisions instead of calling them current policy.
The FAST fact sheet is publicly linked by ABS but carries a `CONFIDENTIAL` footer; that label remains in the original file.

## Proposed HSBC semantic mapping

These mappings are reviewer recommendations. They are not approved links or identifiers shared with the bank.

| Document concept | Existing model field | Review condition |
| --- | --- | --- |
| Debit account | `transactions.sender_account_id` → `accounts.account_id` | Match the payer role, not the literal bank account number |
| Beneficiary account | `transactions.receiver_account_id` → `accounts.account_id` | Preserve the recipient role |
| Remittance currency | `transactions.currency` | Check whether the selected amount is in remittance or debit-account currency |
| Remittance amount | `transactions.amount` | Do not map an unspecified currency amount directly to `payments.amount_sgd` |
| Exchange-rate details | `fx_rates.sgd_rate` | Conceptual context only; the guide does not validate the fixture's fixed rates |
| Requested debit date | No exact equivalent | `payments.booking_date` comes from a UTC timestamp; requested debit date is a different concept |

The form also exposes model gaps: fees, payment purpose, beneficiary bank, and an FX contract are not represented in this fixture.
Blank fields and illustrative values are not new transaction facts.

## Suggested demonstration

```text
Official PDF -> Inspect page -> AI analysis -> Review semantic mapping
                                                |
                                    Attach evidence to draft
                                                |
                                      Validate and publish
```

1. Select **hsbc-smartform-completion-guide** in **Supporting materials**. It is already uploaded locally.
2. Inspect physical pages **4, 5, 7, and 8**.
3. Analyze those pages to understand the form layout and field labels.
4. Check the text and image evidence before reviewing candidate links.
5. Keep the payer, recipient, currency, and amount roles separate.
6. Add a review note that limits the attachment to external field-definition context.
7. Continue with Studio validation and publication only after the mapping is correct.

Candidate document questions after publication:

- “According to the HSBC guide, can the amount be entered in remittance currency or debit-account currency?”
- “According to the HSBC guide, which information identifies the beneficiary?”
- “According to the ABS FAST FAQ dated July 2026, can immediate receipt and the bank's value date differ?”

These questions are prepared examples, not live-LLM verification results.
Keep `total_amount_sgd` and its existing SQL unchanged when adding contextual evidence.
The public documents cannot prove the synthetic total, the fixed USD rate of 1.3, or a particular rejected transaction's cause.

## Image-based document example

Use **HSBC page 4** to demonstrate understanding a real form screenshot.
Use **BIS page 5** for chart interpretation and a possible separate payment-systems model.
The BIS chart measures payment-system characteristics, not customer payment amounts.
Its panels use different populations. Preserve the panel, system type, survey year, percentage unit, and denominator.
Many bars lack exact printed value labels. Do not approve guessed precise percentages from bar heights.
No chart rows were extracted or approved during this preparation.

## Measured importer and matching limits

All six originals are below 5 MiB and have at most 32 pages.
The five bank/ABS documents passed text import in isolated state.
The BIS PDF was accepted as **visual_pending**, with zero text chunks, because the importer encountered an image-bearing page without text.
Select page 5 for AI visual analysis before matching that report. This does not mean its other pages lack text.

Keyword matching produced weak candidates that should not be approved merely because they rank highly:

- HSBC page 5 ranked `payments.amount_sgd` highly, although a remittance amount is not necessarily SGD.
- HSBC page 7 proposed both sender and receiver fields for beneficiary text. Only the recipient role fits that passage.
- FAST text proposed `payments.transaction_id`; a generic product FAQ does not establish a specific transaction identifier.
- DBS page 3 produced no finance candidates in the isolated test. Current similarity ranking does not guarantee the intended conceptual link.

The manifest separates intended concepts from actual generated candidates.
Better role-aware matching or explicit target selection is a follow-up. Do not force an unsuitable link to complete a demo.

The UOB HK transfer-form URL appeared in search but returned HTTP 404 on download, so it is not included.
The UOB Singapore internal-transfer PDF exposed an Adobe dynamic-form placeholder, so it was not selected for this importer.

## Use the HSBC file in the CAI AMP

The repository includes `docs/demo-inputs/finance-real/hsbc-smartform-completion-guide.pdf`.
[Download the included HSBC PDF](https://raw.githubusercontent.com/FerdinandZhong/semantic-hub/main/docs/demo-inputs/finance-real/hsbc-smartform-completion-guide.pdf).
The local demo upload does not automatically populate a new AMP workspace.
The deployed material catalog checked on 19 October did not contain the HSBC guide.

1. Open **Supporting materials** and upload the HSBC PDF.
2. Analyze physical page **7**, then review the beneficiary-account passage.
3. Expand **Add evidence to an existing semantic model**.
4. Find links for the finance model and search `receiver_account_id`.
5. Select the page 7 link to `transactions.receiver_account_id`.
6. Review and approve the link, then apply it to the finance draft.
7. Save, validate, review, and publish the updated model in Studio.

The guide supports the recipient-account role. It does not verify the synthetic transactions.
Use physical PDF page 7; the printed page number differs.
