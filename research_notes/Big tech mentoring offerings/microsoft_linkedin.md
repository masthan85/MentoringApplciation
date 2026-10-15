# Microsoft and LinkedIn AI mentoring, coaching and learning offerings (as of 15 October 2026)

Method note: most WebFetch calls failed with DNS errors (mc.merill.net, learn.microsoft.com, learning.linkedin.com, redmondmag.com). Only the GitHub interview-coach repo page was read in full. Everything else comes from WebSearch result summaries, many of them mirrors of Microsoft Message Center items or third-party blogs. Nothing was checked against a primary Microsoft or LinkedIn page. Treat dates and prices as leads to verify. This note adds to the existing landscape report and does not repeat it. The report cited Microsoft 365 Copilot memory GA as "July 2026" (MC1158329); the newer evidence below suggests that date moved again (see question 4). The report also listed LinkedIn's AI coach as an unsearched gap; this note fills it.

## 1. Microsoft Viva Learning, Learning Agent, Copilot coach agents, Microsoft Learn: shipped vs preview

### Takeaway
The main shipped Microsoft learning-assistant product is the Learning Agent in Microsoft 365 Copilot. It replaced the Viva Learning Copilot experience in a rollout that began in late June 2026. It is employer-licensed, and its more personalised features need a paid Copilot licence. I found no Microsoft-built long-term mentor. The "Career Coach" and other coach agents are templates or built-in agents with unclear status.

### Cited Findings
- Learning Agent in Microsoft 365 Copilot became generally available in June 2026. Message Center MC1450135 says the Viva Learning "Copilot" button now redirects to Learning Agent, and the old side-by-side Copilot view is removed. Worldwide rollout started in late June and finishes by late August 2026, with 15 August 2026 given as the date for all Viva Learning licensed users. — [handsontek mirror of MC1450135](https://m365admin.handsontek.net/?p=23097); [Topedia, June 2026](https://blog-en.topedia.com/2026/06/learning-agent-is-now-generally-available-in-microsoft-365-copilot/) (secondary mirrors of the Message Center item)
- Licensing: capabilities that rely on enterprise grounding (skills assessments, role- and task-based learning scenarios, daily AI tips) require an active Microsoft 365 Copilot licence (sources call it "Copilot (Premium)"). Creating or accessing learning plans made through the agent requires a Viva Learning licence, seeded or premium. — [handsontek / MC1450135 mirror](https://m365admin.handsontek.net/?p=23097)
- AI Skills Navigator content (Microsoft Learn courses, videos, credentials, plus organisational catalogue content) is being added to Learning Agent from mid-August 2026, on by default. — [handsontek](https://m365admin.handsontek.net/?p=23193)
- The next-generation AI Skills Navigator was announced at Ignite as an "agentic learning space" combining content and credentials from Microsoft, LinkedIn Learning and GitHub. The original Navigator launched in late 2024 with courses free of charge. I found no exact date for the next-generation release. — [Microsoft Tech Community Skills Hub](https://techcommunity.microsoft.com/blog/skills-hub-blog/-/4292264); [Microsoft Korea news, Dec 2024](https://news.microsoft.com/ko-kr/2024/12/19/%eb%a7%88%ec%9d%b4%ed%81%ac%eb%a1%9c%ec%86%8c%ed%94%84%ed%8a%b8-ai-%ec%8a%a4%ed%82%ac-%eb%82%b4%eb%b9%84%ea%b2%8c%ec%9d%b4%ed%84%b0-%ea%b3%b5%ea%b0%9c-%ec%a0%84-%ec%84%b8%ea%b3%84-a/). A Redmond Magazine item from June 2026 is titled "Microsoft launches personalized AI learning platform" ([link](https://redmondmag.com/blogs/redmond-dispatch/2026/06/microsoft-launches-personalized-ai-learning-platform.aspx)), but I could not open it, so its content is unverified.
- Microsoft Learn "Plans" are structured, multi-step study paths aimed at Microsoft Credentials. The AI hub offers curated Plans, and Applied Skills are verifiable credentials. These sources date from 2024 to 2025. — [Plans on Microsoft Learn](https://learn.microsoft.com/en-us/training/plans-on-microsoft-learn); [Microsoft Learn AI hub](https://learn.microsoft.com/ai)
- Coach agents: Microsoft's adoption site and blog list a Career Coach agent (personalised career advice, goals, action plans, usable in Teams and Business Chat) and, per a university guide, writing, idea, learning and prompt coaches as customisable starting points. A Microsoft support page frames the Career Coach as aimed at students and educational institutions. Some of these agents need a full Microsoft 365 Copilot licence. — [Microsoft adoption templates (UK)](https://adoption.microsoft.com/en-gb/ai-agents/templates-and-examples); [Agents built by Microsoft](https://support.microsoft.com/en-au/microsoft-365-copilot/agents-built-by-microsoft); [KU CTE guide](https://cte.ku.edu/how-create-copilot-agent). Status labels are ambiguous in the sources, so GA vs preview for the Career Coach is unverified. I found no template named "mentor".
- Viva Insights: manager insights moved to the Viva Insights web app (Sept to Oct 2025 rollout), with a team-scoped Copilot Dashboard (Adoption, Impact and Learning pages). A 2026 item (RM557981) adds Copilot usage metrics "with use cases such as coaching", listed as in development with a June 2026 target. The "coaching" here means managers coaching teams on Copilot adoption. It is not coaching of an individual on their career. — [MC1136039](https://mc.merill.net/message/MC1136039); [RM557981](https://mc.merill.net/message/RM557981)

### Inferences
- Microsoft's learning AI is a catalogue and skills-assessment layer sold to employers. It points users to Learn, LinkedIn Learning and the organisation's catalogue, much like Pluralsight's Iris and DataCamp in the existing report. It is not an individual-owned mentor.
- The coach agents are prompt-and-instruction templates a customer can build in Copilot Studio or Agent Builder (inferred from the template framing). I found no evidence of built-in goal tracking.

### Gaps
- Primary Message Center and Learn pages were unreachable, so exact GA wording is unconfirmed.
- Whether the Career Coach agent is GA, and in which licences, is unverified.
- No evidence found of any Microsoft "learning plan progress over time" feature that reports against career goals rather than course completion.

## 2. LinkedIn: Learning AI coach, Premium career coach, Hiring Assistant, mentorship

### Takeaway
LinkedIn has two shipped AI coaching surfaces: an AI Coaching chatbot inside LinkedIn Learning (sold to organisations) and a Career Coach / job-search assistant for Premium members. Both are scoped to courses or job search. The Hiring Assistant is a recruiter tool. The legacy peer "Career Advice" mentoring feature is reportedly gone.

### Cited Findings
- LinkedIn Learning AI-powered Coaching is a chatbot that answers learner questions in real time and recommends courses and videos from the whole library, reachable from the left navigation as "AI Coaching". It turns the prompt into a search query and may ask clarifying questions. — [LinkedIn Learning business page](https://business.linkedin.com/learn/resources/learner-engagement/linkedin-learning-ai-powered-coaching); [Geneseo help page](https://geneseo.atlassian.net/wiki/spaces/HELP/pages/766640173/AI-Powered+Coaching+LIL)
- Role-play scenarios that admins can customise and assign were listed in August 2025 product updates for availability in September 2025, and generative AI features are being released to all organisations using LinkedIn Learning. — [LinkedIn Learning admin product updates](https://learning.linkedin.com/customer-success-center/product-updates/all-updates/q1-26) (search summary only)
- The University of California Office of the President describes the coach as personalised career and leadership guidance alongside more than 20,000 courses. — [UCOP](https://link.ucop.edu/?p=106829)
- Premium career coach: Business Insider (via Yahoo) reported an AI career coach for Premium members that assesses job fit, researches companies, suggests profile changes and helps with interview prep, in beta at the time. — [Yahoo / Business Insider](https://tech.yahoo.com/ai/articles/linkedin-just-launched-ai-job-153328000.html). A 2026 review says it is not as capable as ChatGPT for open-ended coaching but has full context of your profile and the target job (low-quality, affiliate-style source). — [itsourcecode](https://itsourcecode.com/linkedin/linkedin-ai-job-search-career-coach/)
- Hiring Assistant (recruiter side): reported generally available in English at the end of September 2025, with a February 2026 update adding Teams collaboration and AI follow-ups. Pricing is not public; one competitor guide says it is a negotiated add-on to Recruiter. — [PIN](https://www.pin.com/blog/linkedin-recruiter-new-features/); [Hero Hunt](https://www.herohunt.ai/blog/linkedin-hiring-assistant-2026-cost-and-alternatives/); [LinkedIn](https://business.linkedin.com/talent-solutions/hiring-assistant)
- Mentorship: LinkedIn launched "Career Advice", a free peer mentor-matching feature, in the US, UK, India and Australia in 2017. A third-party 2022 blog claims it was discontinued, with no date or LinkedIn statement. — [TechCrunch, Nov 2017](https://techcrunch.com/2017/11/15/linkedin-rolls-out-its-career-advice-mentoring-program-to-us-uk-and-india/); [Hiration](https://hiration.com/blog/linkedin-career-advice)
- Premium pricing: USD figures vary by source: Career about $29.99 to $39.99 a month and Business $59.99 to $69.99. Sterling figures conflict (Career about £19.99; Business £39.99 or £49.99). No official UK price was found. — [blabla.ai](https://blabla.ai/nl/blog/how-much-for-linkedin-premium); [salesbread](https://salesbread.com/how-much-does-linkedin-premium-cost/) (all low reliability)

### Inferences
- LinkedIn holds the richest profile and job-market data, but its coaches use it for job search and course recommendation. Nothing found suggests goal history or between-session follow-up.

### Gaps
- No LinkedIn primary source was read. UK availability and GBP price of the Premium coach are unconfirmed.
- Current status of Career Advice mentoring is unverified.
- LinkedIn's data handling for the coaches (retention, training use) was not found.

## 3. Azure reference architectures, samples and accelerators

### Takeaway
There is a credible official sample for a multi-session coaching agent (Interview Coach) and a managed long-term memory service in preview. There is no off-the-shelf "career mentor" accelerator.

### Cited Findings
- Azure-Samples/interview-coach-agent-framework (MIT licence): a .NET practice app where a user supplies a resume and job description, gets behavioural and technical questions and feedback, and a summary is saved. It uses Microsoft Agent Framework with a handoff workflow (triage, receptionist, behavioural interviewer, technical interviewer, summariser), Microsoft Foundry for the model, Azure Cosmos DB behind an "InterviewData" MCP server, a MarkItDown MCP server, Aspire for orchestration and optional Azure Container Apps deployment via azd. Chat state is held in the server-side Blazor session, so a refresh starts a new session, while earlier interview records persist. The README warns to review authentication, per-user record access, uploads and retention before using real data. — [GitHub](https://github.com/Azure-Samples/interview-coach-agent-framework) (read directly)
- Memory in Foundry Agent Service: announced at Ignite in November 2025 as a managed long-term memory store, in public preview. Updates add memory item create/read/update/list/delete, default retention (TTL) controls, and integration with Microsoft Agent Framework and LangGraph. Free during preview, with consumption billing from 1 June 2026 (separate rates for short-term events, long-term memories and retrievals). — [Foundry blog, Nov 2025](https://devblogs.microsoft.com/foundry/introducing-memory-in-foundry-agent-service/); [Learn: what is memory](https://learn.microsoft.com/en-my/Azure/foundry/agents/concepts/what-is-memory); [InfoQ](https://www.infoq.com/jp/news/2026/02/foundry-agent-memory-preview). I could not confirm whether it is still preview in October 2026.
- JavaScript AI Buildathon repo lists a community "AI Career Navigator" (resume analysis, skill gaps) using Foundry Agents. Extent of Foundry use is unconfirmed. — [GitHub](https://github.com/Azure-Samples/JavaScript-AI-Buildathon)

### Inferences
- Foundry memory plus Agent Framework plus Cosmos DB is a plausible base for a UK-hosted mentor, but goal tracking, evidence and progress models would have to be built by the product (the sample stores interview records only).

### Gaps
- Learn architecture-centre guides for tutoring or coaching were not found. Foundry region availability (UK South) for memory is unconfirmed.

## 4. Memory, personalisation, privacy, UK data residency

### Takeaway
Microsoft 365 Copilot memory is admin-governed and its GA date has repeatedly slipped. UK in-country Copilot processing was announced for the first wave, but secondary sources raise caveats on routing and third-party models.

### Cited Findings
- Microsoft 365 Copilot memory and personalisation (MC1158329): chat-history-based personalisation, a redesigned Memory settings page, existing admin and user toggles respected. Frontier preview from mid-November 2025. GA dates in successive versions moved from early January 2026 start / July 2026 finish to one version showing mid-September 2026 start / late October 2026 finish. The latest is unconfirmed. This supersedes the "July 2026" in the existing report. — [MC1158329](https://mc.merill.net/message/MC1158329); [itelio](https://www.itelio.com/en/microsoft-message-center/mc1158329)
- Microsoft's November 2025 announcement said Copilot interactions could be processed in-country by end of 2025 in Australia, the UK, India and Japan, with 15 markets by end of 2026. — [IT Brief UK](https://itbrief.co.uk/story/microsoft-to-enable-in-country-copilot-data-processing-by-2026); [Computerworld](https://www.computerworld.com/article/4085303/m365-copilot-data-processing-goes-local-to-meet-sovereignty-demands.html)
- Caveats from lower-quality sources, not confirmed with Microsoft: Claude-generated Copilot output is processed outside the EU Data Boundary once an admin opts in, and EU "flex routing" from 17 April 2026 allows peak-time processing outside the EU. — [cloudswitched](https://www.cloudswitched.com/news/microsoft-365-copilot-anthropic-default-may-2026-uk-business-opt-in-guide)

### Inferences
- UK enterprise tenants get contractual residency, but none of this is user-owned memory; the employer controls it.

### Gaps
- No primary statement on UK residency of Learning Agent or LinkedIn coach data. Not verified whether the UK in-country option has shipped.

## 5. Pricing and UK availability (GBP)

### Takeaway
Everything Microsoft-side needs an employer licence. Sterling figures come from resellers and conflict.

### Cited Findings
- Copilot Business add-on (under 300 users): £16.10 per user per month list in the UK, with a promotional £13.80 reported (end date reported as 31 March 2026 by one source and 30 September 2026 by another); £19.32 on monthly commitment. Full Microsoft 365 Copilot: £23.10 (Syntax) or £24.70 (another blog) per user per month, annual. Copilot Chat is free with eligible plans but lacks grounding in files, email and meetings. Bundled plans with Copilot Business became permanent from 1 July 2026; only USD bundle prices found. — [Syntax](https://www.syntax.co.uk/blog/microsoft-365/microsoft-365-copilot-costs-and-options-for-uk-businesses/); [CloudSwitched](https://www.cloudswitched.com/blog/microsoft-365-copilot-cost-roi-uk-sme-2026); [Compare the Cloud](https://www.comparethecloud.net/articles/getting-microsoft-365-copilot-working-for-a-20-person-uk-company-without-an-enterprise-agreement)
- LinkedIn Premium: see question 2 (unreliable).
- Viva Learning premium price and LinkedIn Learning seat price: not found.

### Gaps
- Microsoft's own UK price page was not read.

## 6. Microsoft's internal mentoring and coaching programmes

### Takeaway
Public documentation is thin and indirect; nothing shows an AI mentor used internally.

### Cited Findings
- Microsoft regional pages describe mentoring tracks for new hires, early-career hires and women's leadership, and Aspire (a 1+ year early-career learning journey) and an HR rotation with senior-leader mentors. — [Microsoft Careers: Aspire](https://careers.microsoft.com/v2/global/en/recentgraduate); [HR rotation](https://careers.microsoft.com/v2/global/en/hrrotation); [Microsoft Thailand news](https://news.microsoft.com/th-th/2018/05/21/leanin_mentorship_en/)
- A Deel blog claims a 70-20-10 learning model and regular manager one-to-ones (third-party, low reliability). — [Deel](https://www.deel.com/blog/employee-development-at-microsoft/)

### Gaps
- No primary documentation of internal AI coaching or mentoring pilots was found.

## 7. What these offerings do not do (gaps against a personal long-term mentor)

### Takeaway
Based on the sources above, none showed an individual-owned, goal-tracking, evidence-based mentor with a chosen persona or human handoff.

### Cited Findings
- Learning Agent plans are tied to Viva Learning licensing and catalogue content. — [handsontek](https://m365admin.handsontek.net/?p=23097)
- LinkedIn's coach is described as weaker than a general assistant for open-ended coaching. — [itsourcecode](https://itsourcecode.com/linkedin/linkedin-ai-job-search-career-coach/) (low reliability)
- Copilot memory is a preference/chat-history feature with admin controls. — [MC1158329](https://mc.merill.net/message/MC1158329)
- The Azure interview-coach sample persists interview records but warns that per-user access and retention are for the adopter to build. — [GitHub](https://github.com/Azure-Samples/interview-coach-agent-framework)

### Inferences
- Absence of evidence, not proof: I did not see goal tracking over months, evidence-backed progress, user-selected persona or lens, or handoff to a human mentor in any Microsoft or LinkedIn product. LinkedIn's old peer mentoring (2017) was the only mentor-matching feature, and it is reportedly discontinued. The best differentiation remains the existing report's: accountability, inspectable memory, honest challenge.
- Microsoft's strength is as a platform (Foundry memory, Agent Framework, Cosmos DB) for building the product, and as a distribution channel via Teams and Copilot.

### Gaps
- Needs primary-source verification of all points before reliance, especially Learning Agent licensing, the Career Coach agent status, Foundry memory GA, UK pricing and UK data-residency.
