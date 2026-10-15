# 10. Countries and regions

Status: accepted

## Context

The product started UK-first. Some behaviour is safety-critical and country-specific (crisis helplines), some is about correctness (time zones, spelling, currency), and some is guidance quality (what is normal about pay, notice and hiring where the user works).

## Decisions

**One definition file per country, not scattered conditions.** `regions.yaml` holds each country's crisis resources, time zone, spelling, currency, retrieval jurisdictions and career notes. Code reads it through `regions/service.py`.

**The crisis message is fixed text built from that file, never generated.** It uses the user's country. When the country is not yet known (for example the first onboarding message) it lists the lines for every supported country rather than assuming one. Onboarding collects the country and the profile cannot be confirmed without it.

**Time zone comes from the user.** The browser's time zone is stored when the user picks a country; the country's usual zone is the fallback and UTC is the final one. Weeks start on Monday everywhere because check-ins are about working weeks.

**The mentor is told where the user works but defers to what they say.** A short prompt section carries the country's norms as orientation, flagged as not legal advice, and says to follow the user if they are working or moving elsewhere.

**Countries are enabled by configuration.** `ENABLED_COUNTRIES` decides what a user can choose. India is defined and evaluated but off until reviewed. Existing profiles in a country that is later disabled keep working.

## Consequences

Adding a country is a data change plus review, not a code change. The review (crisis wording, career notes, content, data-protection advice) is the real cost and is listed in `docs/regions.md`. Crisis detection is still English keyword rules and has not been tuned for other countries' idiom. Everything remains English-only.
