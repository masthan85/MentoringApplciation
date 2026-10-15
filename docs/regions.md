# Countries and regions

The product is built UK-first and works for the United Kingdom, Ireland, the United States and Canada. India is defined and tested but **switched off** until it has been reviewed (see below). Turn it on with `ENABLED_COUNTRIES='["GB","IE","US","CA","IN"]'`.

## What changes by country

Each user has a country, a time zone and a spelling variant on their profile. Choosing a country fills in the other two unless the user has already chosen them. The definitions live in `apps/api/app/modules/regions/regions.yaml`.

| What | How it follows the country |
|---|---|
| Crisis message | A fixed text with that country's emergency number and free helplines. Until a country is known, the message lists the lines for all supported countries |
| Check-in weeks and reminders | Local date in the user's time zone. Weeks start on Monday everywhere, because they are working weeks |
| Spelling | British, American, Canadian or Indian English labels in the voice instructions |
| Mentor prompt | A short "where the user works" section with the country's currency and general working norms (notice, pay conventions, CV or resume, visas). It tells the mentor to defer to the user if they say they are working elsewhere |
| Encyclopedia | Retrieval returns sources tagged `global` or the user's country (Ireland also gets `EU`) |
| Billing | Checkout is asked to charge in the country's currency (GBP, EUR, USD, CAD, INR). Automatic tax (`STRIPE_AUTOMATIC_TAX`) is optional |

Onboarding asks for the country, and the profile cannot be confirmed without it. It can be changed later in Settings.

## What has not been done, and who must do it

Everything below needs a person, not more code.

1. **Crisis wording and numbers, per country.** The numbers were taken from search results on 15 October 2026, not from the services' own pages. A qualified person in each country must confirm them and the wording before launch there. India's older KIRAN line (1800-599-0019) was left out because sources disagree on whether it still runs separately from Tele-MANAS (14416). The crisis *detection* rules are English-only and were written with UK phrasing; they have not been tested on idiom from other countries.
2. **Career notes.** The short working-norms notes in `regions.yaml` are general orientation, written without local review. Someone who works in each market should correct them.
3. **Encyclopedia content.** The 15 starter sources are global and unreviewed. Country-specific sources (for example notice periods, CTC structure, resume norms) need to be written or licensed, tagged with `jurisdiction`, and reviewed.
4. **Data protection, per country.** Needs a lawyer. In outline:
   - UK: UK GDPR, the Data Protection Act 2018 and the Data (Use and Access) Act 2025.
   - Ireland: EU GDPR. The EU AI Act applies to EU users (see the research report for dates, which rest on secondary sources).
   - US: no single law. California and other states have privacy laws, and some regulate automated decisions and employment tools. Treat this as a state-by-state question.
   - Canada: PIPEDA plus provincial laws (Quebec's is the strictest), and French-language requirements in Quebec.
   - India: the Digital Personal Data Protection Act 2023. Check its current rules on consent notices, children, and any data-location requirements before launch.
   Privacy notice, consent wording and data processing records need to be per jurisdiction. Where data is stored (UK South today) is a decision, not a default: moving US or Indian users' data to a nearer region may be sensible or required.
5. **Language.** Everything is English only. Indian English is a spelling label, not a translation; Hindi and other Indian languages, and French for Canada, would need the prompts, safety rules and evaluation scenarios redone.
6. **Money.** Prices in each currency must be created in Stripe (as currency options on each price) before `BILLING_ENABLED` is turned on. Tax registrations are needed for automatic tax to work.
7. **Evaluation.** `evals/scenarios/regions.yaml` checks the crisis text and prompt content per country (including India). The judged rubrics need a full run with real models and a human reading of the results.

## Adding a country

1. Add an entry to `regions.yaml` with its crisis resources, time zone, currency, jurisdictions and career notes.
2. Add its `jurisdiction` code to `JURISDICTIONS` in `encyclopedia/parsing.py` if it is new.
3. Add scenarios to `evals/scenarios/regions.yaml`.
4. Get the review in the list above, then add it to `ENABLED_COUNTRIES`.
