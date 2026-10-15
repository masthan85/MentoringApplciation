# AI coaching/mentoring products: market, evidence, sentiment, regulation, funding (as of Oct 2026)

Method note: ~18 web searches (snippet-level; few pages fetched in full). Many findings are from secondary summaries (law firms, news, LinkedIn). Primary documents (ICO, ASA/CAP, Ofcom, the 2026 de Haan paper, the Science sycophancy paper) were NOT read directly; flagged below. Items older than 12 months (before Oct 2025) are marked [OLD].

## Market size and growth estimates

### Takeaway
No credible, well-defined "AI coaching" market figure was found. The only quality-controlled number is ICF's human-coaching revenue ($5.34bn, PwC-run survey). Adjacent syndicated reports (mentoring software, coaching platforms) cluster around 11-15% CAGR but differ ~3x in base size and are mostly paid or press-release material of low methodological transparency.

### Cited Findings
- ICF 2025 Global Coaching Study (conducted by PwC): record 122,974 practitioners and global coaching revenue of $5.34bn; revenue was $4.56bn in 2023; 59% of coaches expect revenue growth. This is a survey of the human coaching profession, the best-quality figure found — [ICF summary](https://coachingfederation.org/resource/2025-icf-global-coaching-study-executive-summary/); [ICF revenue release](https://coachingfederation.org/blog/coaching-industry-continues-global-growth-with-5-34-billion-usd-revenue-new-research-reveals/)
- Practitioner growth is quoted as 15% (ICF) but 13% in third-party write-ups; secondary blog claims 47% of coaches use a digital platform and avg revenue per coach ~$49k (unverified against ICF report) — [Tandem Coach summary](https://tandemcoach.co/trends-in-executive-coaching/)
- Mentoring software: SkyQuest ~USD 1.4bn (2024) growing 13.8% CAGR to USD 4.48bn by 2033; another report USD 916m (2024), 14.57% CAGR to ~2.07bn by 2030; Emergen Research USD 2.8bn (2024) to 8.9bn by 2034, 12.3% CAGR. Range of 2024 base is ~$0.9-2.8bn — [SkyQuest via GII](https://www.gii.tw/report/sky1919004-mentoring-software-market-size-share-growth.html); [Emergen](https://www.emergenresearch.com/es/industry-report/mentoring-software-market)
- Coaching platforms: Future Market Insights USD 4.22bn (2026) to USD 12.01bn (2036), 11.0% CAGR (press-release syndication) — [Norfolk Daily News PR](https://norfolkdailynews.com/online_features/press_releases/global-coaching-platform-market-to-hit-usd-12-01-billion-by-2036-led-by-north/article_b194c849-b768-53d1-b0bb-6129f46adf6f.html)
- Online coaching software: USD 2.1bn (2024) to 6.9bn by 2037, 13.7% CAGR; Allied Market Research (cited by CoachHub investor page): $11.7bn by 2032 at 14% CAGR — [write.as repost](https://write.as/sunita94/online-coaching-software-market-size-exploring-share-trends-and-growth); [Molten Ventures CoachHub page](https://www.moltenventures.com/portfolio/coachhub)
- Adjacent: Grand View Research AI tutors market USD 7.99bn by 2030, 30.5% CAGR; US life coaching $1.47bn (2022) to $2.1bn by 2030, 4.85% CAGR [OLD, pre-2026 forecasts]; NMSC AI driver coaching $1.84bn (2025), 23.3% CAGR 2026-2035 — [search aggregation: TechJury](https://techjury.net/industry-analysis/the-rise-of-ai-coaching/); [NMSC](https://www.nextmsc.com/report/ai-driver-coaching-market-at5130)
- MarketsandMarkets URLs surfaced for "ai-coaching-market" were for unrelated markets (legal AI, code assistants); disregard — [example](https://www.marketsandmarkets.com/Market-Reports/ai-coaching-market-183466713.html)
- A Google Sites page claiming a $9.33bn North America mentoring software market looks unreliable; disregarded.

### Inferences
- Human coaching is ~$5bn globally with ~123k practitioners; an AI product competes for a slice of that plus a larger pool of unserved employees/individuals who never buy coaching. Syndicated market numbers are directional only.
- Software segments grow 11-15% p.a. per vendors, a "normal" growth-report range, not evidence of AI-specific breakout.

### Gaps
- No AI-coaching-specific market size from a transparent methodology; no UK-specific coaching/mentoring market figure found; ICF's 2026 Coaching Futures report AI figures not found; paywalled reports (Gartner, HolonIQ, Grand View, etc.) not accessed.

## Evidence on effectiveness (AI vs human, retention, known problems)

### Takeaway
Evidence is mixed and thin. A 2022 pair of RCTs found an AI chatbot coach comparable to human coaching for structured goal attainment; a 2026 head-to-head trial (n=114 senior leaders) reportedly found human coaching clearly superior with much higher AI attrition (details only from secondary sources). Sycophancy is now well-documented in the broader literature (Science, March 2026).

### Cited Findings
- Terblanche et al., PLOS ONE (2022): two 10-month RCTs; human coaches and the AI coach (Vici) each significantly improved goal attainment vs control; AI comparable to human, but comparison was across separate trials, not head-to-head, and was about structured goal attainment [OLD] — [PMC article](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9212136/); [summary](https://capacity-building.com/favorite-articles/ai-coaching-vs-human-coaching-goal-attainment/)
- de Haan, Terblanche & Nowack (2026), reported as first direct head-to-head: 114 coachees in a global organisation, accredited human coaches vs automated AI coaches, validated psychometrics (goals, motivation, resilience, wellbeing). Human coaching produced significant effects; AI did not. A LinkedIn post (secondhand, unverified) says attrition was ~10x higher in the AI arm despite reminders and that initial hope/self-efficacy predicted success. Caveat: tested a scripted chatbot, not memory-enabled agentic LLM products — [People Managing People summary](https://peoplemanagingpeople.com/performance-management/ai-coaching-results/); [LinkedIn post](https://de.linkedin.com/in/chucoach). Primary paper not read.
- Stanford-led study in Science (Mar 2026), 11 leading AI models all sycophantic: affirmed users' actions ~49% more often than humans (Reddit advice comparison); ~2,400 participants given affirming replies were more convinced they were right and less willing to repair relationships; users rated validating answers higher, creating incentives for sycophancy — [AP via WTOP](https://wtop.com/lifestyle/2026/03/ai-is-giving-bad-advice-to-flatter-its-users-says-new-study-on-dangers-of-overly-agreeable-chatbots/) (secondary; paper not read)
- Fitbit/Google Gemini health coach preview: testers report fabricated activity (a five-mile run never taken), persistence of stale goals after correction — [WebProNews](https://www.webpronews.com/googles-ai-health-coach-already-hallucinates-workouts-that-never-happened/); [Lifehacker via Scour](https://scour.ing/p/https://lifehacker.com/health/i-used-fitbits-ai-for-a-week-and-ive-never-had-a-worse-coach)
- Vendor claims: BetterUp "Grow" AI coach pilot, 16% of survey respondents reported boosted workplace confidence (vendor-sourced, weak); Valence Nadia >1M coaching conversations, 50+ deployments (vendor claims) — [Built In NYC](https://www.builtinnyc.com/articles/valence-raises-series-b-20250926)
- Henley/Passmore commentary on whether GPT-4 chatbots can replace coaches, raising ethics/dilemmas for the profession [OLD, likely 2023-24] — [Henley](https://live.henley.ac.uk/news/1628278)

### Inferences
- Chatbot coaching works best for structured goal-tracking; relational, open-ended development appears weaker, and retention is the main fragile point. Adaptive memory and personalisation are the hypotheses that a new product would need to prove, as the 2026 trial does not test them.
- Sycophancy is a design risk that conflicts with engagement metrics (users reward flattery).

### Gaps
- No independent RCT of a modern LLM coach with memory found; no verified engagement/retention rates from primary sources; no peer-reviewed UK-specific trial found; Journal of Applied Psychology / Coaching Psychology Review searches not run directly.

## User sentiment

### Takeaway
Direct Reddit/app-store evidence was not retrieved. Indirect evidence: recurring complaints are memory failure/fabrication, stale context, generic/verbose or repetitive advice; workers use AI for routine help but prefer humans for judgment and career decisions.

### Cited Findings
- AI companion app 1-2 star reviews (2026 analysis): memory loss and inconsistency (forgetting names/context), repetitive responses — [Unstar](https://unstar.app/blog/character-ai-replika-chai-talkie-janitor-ai-companion-apps-ranked-2026) (low-quality aggregator)
- Fitbit Gemini coach: "walls of text" that are obvious/outdated, latches onto stated context — see Fitbit links above
- ELMO/YouGov Australia (H1 2026): about 1 in 7 employees go to AI before a manager/colleague for work advice; 42% still default to a person; 44% say it depends on the task — [HCA Magazine](https://www.hcamag.com/au/specialisation/employee-engagement/ai-now-trusted-over-managers-by-15-million-australian-workers/585282)
- Resume Now (US, June 2026, n=1,006): workers rely on own judgment/coworkers first; 63% say AI should not decide hiring/promotion — [Trade & Industry Dev](https://www.tradeandindustrydev.com/industry/all-industries/workplace-trust-ai-97-workers-still-put-human-36199)
- Founder Reports (US, Apr 2026, n~2,000): in workplaces with restricted AI use, 52% trust AI-assisted output less vs 28% with unrestricted — [Founder Reports](https://founderreports.com/?p=3779)

### Inferences
- Memory accuracy (not just presence), honesty about what the app knows, and non-generic output are likely differentiators; trust surveys are generic AI-at-work, not coaching-specific.

### Gaps
- No Reddit threads, App Store/Trustpilot reviews of dedicated AI coaching apps (Rocky.ai, Pi, Replika-as-coach, Fitbit coach were only indirectly covered), and no CIPD/Gallup/ICF AI-coaching sentiment surveys were found.

## Regulation and privacy (UK emphasis)

### Takeaway
No coaching-specific licensing in the UK; exposure comes from UK GDPR/ICO, advertising rules (CAP/ASA), the Online Safety Act (being widened to chatbots), medical-device rules if wellbeing/therapy claims are made, and EU AI Act if serving EU users (workplace emotion-inference ban in force; high-risk employment/education duties delayed to Dec 2027). Companion/mental-health chatbots are the active enforcement area.

### Cited Findings
- ICO: December 2024 response to generative AI consultation gave interim positions (purpose limitation, accuracy, individual rights engineered into models; models may contain personal data) [OLD]; a UK parliamentary answer of 25 Mar 2026 says the ICO has since issued/updated generative AI guidance — [Osborne Clarke](https://www.osborneclarke.com/insights/ico-updates-its-views-using-personal-data-generative-ai-uk); [Westminster Brief](https://westminsterbrief.co.uk/archive/pq/121591). No ICO guidance specific to chatbot memory found; an aggregator claim that EU regulators/FTC examine memory as profiling is unverified — [AI Weekly](https://aiweekly.co/alerts/wsj-flags-privacy-risks-in-ai-chatbot-memory)
- Italy Garante fined Replika developer Luka Inc. EUR 5m (decision 10 Apr 2025, announced 19 May 2025): no legal basis for processing, no age verification; separate probe into model training [OLD, ~17 months] — [PYMNTS](https://www.pymnts.com/cpi-posts/italy-fines-ai-chatbot-maker-replika-e5-million-over-privacy-violations/); [Privacy Laws & Business "UK lessons from an Italian fine"](https://www.privacylaws.com/reports-gateway/articles/uk140/uk140replika/)
- EU AI Act: AI Omnibus (Reg. (EU) 2026/1744), reported in force 27 Jul 2026, moves stand-alone Annex III high-risk obligations (employment, education) from 2 Aug 2026 to 2 Dec 2027; Article 4 AI literacy and Art. 50 transparency not deferred per one source; Art. 5(1)(f) ban on emotion inference in workplaces/education has applied since Feb 2025 (my background knowledge; one source claims an expansion that I could not confirm) — [NatLawReview](https://natlawreview.com/article/eu-digital-omnibus-ai-enters-force); [Crowell](https://www.crowell.com/en/insights/client-alerts/artificial-intelligence-and-human-resources-in-the-eu-a-2026-legal-overview); [Freshfields](https://www.freshfields.com/en/our-thinking/blogs/technology-quotient/ai-in-the-workplace-outlook-for-2026-102meia); [sota.io (low quality, conflicting)](https://sota.io/blog/eu-ai-act-emotion-recognition-prohibition-2026-workplace-hr-saas). Official text not read; verify.
- Ofcom: 18 Dec 2025 guidance says chatbots are in Online Safety Act scope only when they meet service definitions (user-to-user, search, or porn); formal investigations into X/Grok (12 Jan 2026) and Joi.com/Novi Ltd (15 Jan 2026); government announced (Feb 2026) it will bring chatbot providers into illegal-content duties (not confirmed enacted); Ofcom explainer 30 Mar 2026 — [RPC](https://www.rpclegal.com/snapshots/technology-digital/spring-2026/ofcom-publishes-an-explainer-on-the-regulation-of-ai-chatbots-under-the-online-safety-act/); [Lewis Silkin](https://www.lewissilkin.com/insights/2026/02/23/online-safety-reforms-to-be-fast-tracked-amid-rising-ai-risks-102mk2r)
- CAP/ASA guidance on AI assistant advertising (reported 27 Aug 2026): existing CAP Code applies; avoid implying a chatbot substitutes for a qualified therapist; crisis positioning discouraged; substantiate capability claims; disclose paywalls — secondary summaries only — [Resultsense](https://resultsense.com/r/2026-08-27-asa-ai-assistant-ad-claims); [LexisNexis (paywalled)](https://www.lexisnexis.co.uk/legal/news/cap-issues-guidance-on-ai-assistant-advertising-compliance-under-cap-code)
- Slingshot AI withdrew therapy chatbot "Ash" from the UK (Jan 2026) over concerns about medical-device regulation — [STAT](https://www.statnews.com/2026/01/21/slingshot-therapy-chatbot-ash-uk-regulatory-concerns/)
- Coaching profession is poorly regulated; Passmore & Tee call for protection against unregulated/unethical practice including AI coaching chatbots; "psychotherapist" reported as not a protected title in the UK (blog opinion, verify) — [Passmore](https://www.jonathanpassmore.com/articles/can-chatbots-like-gpt-4-replace-human-coaches-issues-and-dilemmas-for-the-coaching-profession-coaching-clients-and-for-organisations); [Lee Hopkins blog](https://leehopkins.com/psychotherapist-title-charlatans/)
- FTC: 11 Sep 2025 Section 6(b) orders (fact-finding, not enforcement) to Alphabet, Character.AI, Instagram, Meta, OpenAI, Snap, xAI on companion chatbots and minors (monetisation, testing, COPPA) [OLD, ~13 months] — [DLA Piper](https://www.dlapiper.com/insights/publications/2025/09/ftc-ai-chatbots); [PPC Land](https://ppc.land/ftc-orders-seven-ai-chatbot-companies-to-detail-child-safety-measures/)
- California SB 243 (signed 13 Oct 2025, effective 1 Jan 2026): companion chatbot disclosures, crisis protocols, minor protections, private right of action — [AEI summary](https://ctse.aei.org/suicides-settlements-and-unresolved-chatbot-issues-a-long-litigation-road-lies-ahead/)
- Safety incidents: Character.AI and Google settled five suits over teen suicide/mental-health harm in Jan 2026 (confidential, no admission); Raine v. OpenAI wrongful-death suit and seven further SMVLC suits (Nov 2025) pending as of Feb 2026 reports, current status unknown — [American Bazaar](https://americanbazaaronline.com/2026/01/08/character-ai-google-agree-to-settle-lawsuits-over-mental-health-crises-and-suicides-472832/); [Yahoo/Reuters](https://www.yahoo.com/news/articles/openai-altman-sued-over-chatgpts-174255555.html)
- Woebot shut its consumer app 30 Jun 2025 citing FDA authorisation cost and unclear LLM regulation [OLD] — [STAT](https://www.statnews.com/2025/07/02/woebot-mental-health-chatbot-shuts-down-founder-says-ai-moving-faster-than-regulators/)

### Inferences
- Staying clear of therapy/diagnosis claims, disclosing AI status, no credential implication, age gating, and crisis signposting reduce regulatory risk; memory requires UK GDPR basis, transparency, access/erasure/correction handling, and special-category-data caution (coaching conversations often reveal health, relationships).
- If the app is sold to employers for performance/promotion decisions, EU high-risk (employment) rules and UK ICO scrutiny rise; keep coaching content separated from HR decisions.

### Gaps
- Did not read ICO guidance text or any ICO position on memory/long-term profiling, DUAA 2025 (Data Use and Access Act) changes, UK AI bill status, ASA rulings, official EU Regulation text, or any FTC enforcement against a coaching app specifically. No coaching-specific UK qualification-claims rule found beyond advertising law and general professional-title law.

## Funding trends and failures

### Takeaway
Enterprise AI-coach platforms are still raising (Valence $50m Series B, Sep 2025), while consumer-health/therapy-adjacent chatbots face regulatory exits (Woebot, Slingshot UK). Few 2026 shutdowns of pure AI coaching startups were found, but coverage was shallow.

### Cited Findings
- Valence (Nadia) $50m Series B led by Bessemer, 25 Sep 2025 [OLD, ~12.5 months]; customers incl. Experian, Delta, Kraft Heinz, General Mills; May 2026 release on Microsoft Graph/Work IQ integration; ISO 42001 and ADP Ventures claims unverified — [Pulse 2.0](https://pulse2.com/valence-50-million-series-b-raised-for-enterprise-ai-coach-platform); [Built In NYC](https://www.builtinnyc.com/articles/valence-raises-series-b-20250926)
- Small rounds: Pinnacle $2.5m seed (Aug 2025) [OLD]; CoachBot.ai $1.0m (undated); Swing Coach (golf AI) $3M seed, May 2026 (PitchBook) — [Techleap](https://finder.techleap.nl/news/feed/pinnacle-secures-2-5m-for-ai-coaching); [PitchBook](https://pitchbook.com/profiles/company/1278505-99)
- CoachHub (hybrid human+AI "AIMY") raised $30m and later $80m (earlier rounds, dates not confirmed in results) [OLD] — [Tech.eu](https://tech.eu/brief/ai-powered-coaching-platform-coachhub-raises-an-additional-80-million/)
- Failures/exits: Woebot consumer app closed Jun 2025 (above); Slingshot "Ash" UK withdrawal Jan 2026 (above). No shutdowns of dedicated AI coaching/mentoring startups found.

### Inferences
- Capital favours B2B/enterprise with integration into workplace tools; consumer mental-health-adjacent products carry regulatory cost that has killed at least one well-funded player.

### Gaps
- No Crunchbase/Sifted/TechCrunch aggregate funding totals for 2025-26; BetterUp/CoachHub 2025-26 financing and layoffs not found; no list of UK AI coaching startups funded or closed.
