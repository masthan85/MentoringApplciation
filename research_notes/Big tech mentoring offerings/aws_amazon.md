# Amazon / AWS AI mentoring, coaching, career-development and learning offerings (as of 15 Oct 2026)

Method note: every WebFetch failed with DNS errors (getaddrinfo ENOTFOUND for aws.amazon.com, docs.aws.amazon.com, mitsloanme.com), so no primary page was read in full. All findings below come from search-result summaries of the cited URLs. Treat them as medium or low confidence until checked on the vendor page. Nothing here repeats the existing landscape report (reports/AI mentoring apps landscape 2026.md); that report never covered AWS, Amazon, Kiro, Alexa+ or Coursera/LinkedIn-style learning assistants from Big Tech, so this is additive. Nothing contradicts it.

## 1. AWS Skill Builder, Training and Certification, AWS Educate, AI Ready

### Takeaway
AWS has the deepest free/low-cost technical learning catalogue of any hyperscaler and added AI features in 2025-26 (Lab Maker, Meeting Simulator, AI-powered Cloud Quest, a lab learning assistant). These are catalogue-bound, AWS-only skill training with no persistent mentor relationship, goals model or human handoff. Current GBP pricing was not found.

### Cited Findings
- Lab Maker (reported May 2026): an AI-powered Skill Builder feature that generates personalised labs for popular AWS services from a plain-language goal, with guided steps overlaid on a simulated AWS console — [search summary citing AWS Training and Certification blog](https://aws.amazon.com/blogs/training-and-certification/?trk=sm); I did not read the post, so the exact launch date is unverified.
- Skill Builder Meeting Simulator: creates virtual conversations with AI personas (sceptical executives to domain experts) to practise presenting AI solutions to leaders; also reported that Skill Builder offers 220+ free AI courses, covering intro to generative and agentic AI — [MIT Sloan Management Review MENA](https://www.mitsloanme.com/article/aws-rolls-out-new-tools-to-build-job-ready-ai-skills/) (secondary press coverage; date not confirmed).
- AI assistant for hands-on labs (reported Dec 2024): covers 200+ self-paced labs in AWS Builder Labs and Digital Classroom courses, for Individual and Team subscribers, English only — [DevelopersIO/Classmethod](https://dev.classmethod.jp/articles/aws-skill-builder-learning-assistant-ai/). Whether it is unchanged in Oct 2026 is unconfirmed.
- Cloud Quest was relaunched with an AI-powered customer conversation at its centre; every learner including free-tier can relaunch completed labs; completion earns official AWS badges (e.g. Cloud Practitioner) — [AWS Training and Certification blog](https://aws.amazon.com/blogs/training-and-certification/introducing-the-new-aws-cloud-quest-ai-powered-practice-hands-on-building-and-a-path-to-official-aws-badges/). Date not given in the snippet.
- Exam prep is structured as 4-step plans: free practice question sets and Domain Review courses, plus subscription content (official practice exams, Domain Practice courses, AWS SimuLearn) — [AWS blog, January 2026 new offerings](https://aws.amazon.com/blogs/training-and-certification/january-2026-new-offerings). The same post lists four new Builder Labs and two classroom courses on agentic AI in Jan 2026.
- Pricing (USD only found): individual subscription launched at $29/month or $299/year with three practice exams — [TechCrunch via search](https://techcrunch.com/?p=2364143). AWS promo terms say $299 was a first-year promotional price and the regular annual rate is $449 from year two (promotion dated Jan-Mar 2024) — [AWS promotional terms](https://aws.amazon.com/training/skill-builder-promotional-terms-conditions/). Team plan listed at $449/seat/year, minimum 5 seats — [AWS pricing page snippet](https://aws.amazon.com/training/digital/pricing/?nc1=h_ls). Conflicting and possibly stale; no GBP price found. A 7-day free trial auto-converts to $29/month if not cancelled — [AWS trial terms](https://pages.awscloud.com/GLOBAL-Other-GC-Skill-Builder-Subscription-Free-Trial-Terms-and-Conditions.html) (2023 page).
- AWS AI & ML Scholars 2026 is powered by Skill Builder; graduates get up to three months of access; application window 24 Mar to 24 Jun 2026 — [Udacity](https://www.udacity.com/scholarships/aws-ai-ml-scholarship).
- AI Ready: announced Nov 2023, goal of free AI skills training for 2 million people by end 2025; eight new free courses added to 80+ existing, plus Udacity scholarships (>$12M value, 50,000+ students) and up to $8M credits to Code.org — [Business Wire](https://www.businesswire.com/news/home/20231119572231/en/Amazon-Announces-%E2%80%98AI-Ready%E2%80%99-a-New-Initiative-Designed-to-Provide-Free-AI-Skills-Training-to-2-Million-People-by-2025). Outcome versus the 2 million target not found.

### Inferences
- Skill Builder's AI is a tutor and simulator for AWS skills; it is not a cross-session mentor. No evidence in my results of persistent user memory, goal tracking, or a human mentor handoff.
- Persona-based role-play (Meeting Simulator) is the closest AWS analogue to a "lens" or practice partner, and a design pattern worth noting.

### Gaps
- UK/GBP Skill Builder pricing and current individual price (fetch failed).
- Whether Skill Builder offers personalised learning plans beyond exam-prep plans; AWS Educate 2026 changes (none found).
- Official dates for Lab Maker and the Meeting Simulator.

## 2. Amazon Q Developer, Q Business, Kiro, PartyRock, Bedrock Agents / AgentCore / Strands reference material

### Takeaway
AWS offers building blocks (AgentCore Memory, Strands, Q Business) and an education-agents reference post, but I found no AWS sample or blueprint for a career coach or mentor. Q Developer and Kiro are coding tools with no found coaching mode.

### Cited Findings
- No coaching or tutor mode found for Kiro or Q Developer. Aggregators list Q Developer Pro at $19/user/month (reportedly cut from $25 on 4 Feb 2026) and Kiro credit tiers (Free 50 credits, Pro $20, Pro+ $40, Pro Max $100, Power $200) — [CostBench](https://costbench.com/changelog/amazon-codewhisperer-price-decrease-2026-02/), [StackPick](https://www.stackpick.net/pricing/kiro/). Aggregators, low confidence.
- Single-source claim: Q Developer IDE plugins and paid subscriptions reach end of support on 30 Apr 2027, with Kiro as successor; console and Slack/Teams chat stay — [innFactory](https://innfactory.de/en/cloud/aws/products/q-developer/). Unverified, flag as such.
- PartyRock: free app-builder playground on Bedrock; recurring daily free credits, no card or AWS account needed per vendor/directory pages; AWS recommends moving to Bedrock for production — [innFactory](https://innfactory.de/en/cloud/aws/products/partyrock/), [AWS What's New 2023](https://aws.amazon.com/about-aws/whats-new/2023/11/partyrock-amazon-bedrock-playground/). Exact 2026 daily allowance not found.
- AWS ML blog "Build and scale adoption of AI agents for education with Strands Agents, Amazon Bedrock AgentCore, and LibreChat": institutional agents (e.g. course planning needing transcript, prerequisites, schedule checks), Strands for agent logic, AgentCore Runtime to scale, LibreChat as UI — [AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/build-and-scale-adoption-of-ai-agents-for-education-with-strands-agents-amazon-bedrock-agentcore-and-librechat); third-party summary lists LMS/SIS integration and FERPA/GDPR as challenges — [CloudThat](https://www.cloudthat.com/resources/blog/transforming-education-with-aws-strands-agents-bedrock-and-librechat). I did not confirm whether a runnable repo is attached.
- AgentCore Memory: short-term session memory plus configurable long-term memory (preferences, cross-session knowledge); works with Strands and other frameworks; hands-on lab in aws-samples — [aws-samples/sample-getting-started-with-amazon-agentcore](https://github.com/aws-samples/sample-getting-started-with-amazon-agentcore), [AWS docs](https://docs.aws.amazon.com/fr_fr/bedrock-agentcore/latest/devguide/memory.html). Use-case samples in awslabs/amazon-bedrock-agentcore-samples include a customer-support assistant with memory, no career coach found — [SourcePulse](https://www.sourcepulse.org/projects/11033485).
- Q Business HR: AWS Solutions Library guidance for HR assistants (Q application, data sources, custom plugin to an HR system) — [AWS Guidance](https://aws.amazon.com/solutions/guidance/ai-assistants-with-amazon-q-business/); AWS ML blog says Q Business does not use customer data to train models and supports topic guardrails — [AWS ML Blog](https://aws.amazon.com/blogs/machine-learning/build-a-generative-ai-assistant-to-enhance-employee-experience-using-amazon-q-business). Use case is policy Q&A, not career development.

### Inferences
- A mentor product on AWS would be assembled from Strands + AgentCore Memory + Bedrock; AWS provides no mentoring-specific blueprint, so goal model, evidence tracking and persona logic must be custom.

### Gaps
- Whether any aws-samples/awslabs repo for coaching, tutoring or HR career agents exists (search index did not show one; direct GitHub search not done).
- AgentCore Memory unit prices (only third-party figures, ambiguous; AWS page not read). Q Business current pricing and status not checked.

## 3. Amazon employee programmes, Alexa+ and consumer uses

### Takeaway
Career Choice is documented (tuition pre-payment, not coaching). Alexa+ is live in UK Early Access with cross-conversation memory but no coaching feature found.

### Cited Findings
- Career Choice UK: Amazon UK says it pre-pays up to 100% of tuition for nationally recognised courses, up to £3,000 a year, and 23,000+ UK employees have participated as of 2025 — [Amazon UK](https://www.aboutamazon.co.uk/workplace/upskilling). Older 2024 coverage gave 95% of fees, up to £8,000 over four years — [Retail Gazette](https://www.retailgazette.co.uk/?p=165312); the two conflict, the newer page likely supersedes. £23M further UK skills investment announced June 2024 — [Retail Bulletin](https://www.theretailbulletin.com/general-merchandise/amazon-to-invest-a-further-23-million-in-skills-training-for-uk-employees-19-06-2024/).
- US: Career Choice extended to corporate employees in January 2026 (launched 2012 for operations staff) — [About Amazon](https://www.aboutamazon.com/news/workplace/amazon-career-choice-training-programs-tuition-careers). UK applicability to corporate staff not found.
- Alexa+ UK: Early Access launched 19 March 2026; free for Prime; reported standalone price £19.99/month for non-Prime after Early Access, with free access for all reported through at least 15 Sep 2026 — [Silicon UK](https://www.silicon.co.uk/e-innovation/artificial-intelligence/amazon-alexa-uk-629179), [Cord Cutters News](https://cordcuttersnews.com/amazons-alexa-launches-in-the-uk/). Marketed as remembering past conversations across devices and proactive; Alexa.com reached UK Early Access users 20 July 2026. Whether the £19.99 plan has started is unconfirmed.
- No Amazon "career coaching" or Leadership-Principles-based mentoring programme found publicly documented in my searches.

### Inferences
- Alexa+ is the only Amazon product found with consumer-facing cross-conversation memory, but it is a home assistant, not a goal-tracking mentor.

### Gaps
- Internal Amazon mentoring and coaching programmes; any Alexa+ coaching skills.

## 4. Memory, privacy, UK data residency

### Takeaway
UK in-region processing exists for some pieces: AgentCore Memory is in London, and newer Claude models on Bedrock list London in-region inference. Details vary by model and feature, so verify in-account.

### Cited Findings
- AgentCore regional support: AWS's supported-regions page places Europe (London) among regions supporting Gateway, Identity and Memory only (not full feature set) — [AWS docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html) (via search summary). AgentCore cross-region inference pages also list London — [AWS docs](https://docs.aws.amazon.com/de_de/bedrock-agentcore/latest/devguide/cross-region-inference.html). Secondary tracker: 20 of 37 regions — [AWS Fundamentals](https://awsfundamentals.com/regions/service/amazon-bedrock-agentcore).
- Bedrock Claude in London: the Claude Opus 4.6 model card lists eu-west-2 with In-Region, Geo and Global inference; the Opus 4.5 card lists London as Geo and Global only — [Opus 4.6 card](https://docs.aws.eu/bedrock/latest/userguide/model-card-anthropic-claude-opus-4-6.html), [Opus 4.5 card](https://docs.aws.eu/bedrock/latest/userguide/model-card-anthropic-claude-opus-4-5.html). Geo routing may move data between EU regions; single-Region needs an application inference profile and IAM region condition — [AWS ML Blog, August 2026](https://aws.amazon.com/blogs/machine-learning/enforcing-data-residency-with-single-region-claude-code-on-amazon-bedrock). A mirror notes the newer Mantle endpoint lacked in-region London routing (internally inconsistent source, low confidence).
- Q Business states customer data is not used to train models (see section 2).

### Inferences
- A UK mentor built on AgentCore Memory with in-region Claude could claim UK data residency, but only for specific model and endpoint combinations; EU geo profiles are not UK-only.

### Gaps
- UK adequacy/DPA specifics, retention/deletion controls for AgentCore long-term memory, and per-user memory inspection and editing (not covered in my sources).

## 5. What AWS/Amazon does NOT do (versus a personal long-term mentor)

### Takeaway
Based on the evidence found, AWS offerings cover content, practice and plumbing, not the mentor relationship.

### Cited Findings
- Skill Builder AI features are scoped to AWS content and labs (sections 1). Alexa+ memory is conversational, not goal-linked (section 3). Q Business HR guidance is policy Q&A (section 2). AgentCore Memory provides primitives only (section 2).

### Inferences
- Not found in any source: user-owned goal tracking, evidence-based progress records, selectable mentor persona or lens for career coaching, human mentor handoff, or an AWS career-coaching blueprint. These are absence-of-evidence conclusions from search summaries, medium-low confidence.
- Opportunity: AWS gives infrastructure (memory, UK region, Strands) and a UX pattern (persona role-play) to reuse; differentiation must come from goal model, evidence trail and human referral.

### Gaps
- No primary-page verification of any claim; no independent reviews or usage data on Skill Builder AI features; no Computer Weekly/UKTN/The Register coverage found.
