# Literature notes for Study 1 v2 (real funds)

Summaries are in my own words, based only on each paper's abstract or landing page, read on 2026-10-19.
**Verify against the abstract (and ideally the full paper) before citing.** None of these were read in
full yet.

**Positioning.** Study 1 v2 is a *domain transfer* of agentic-choice and LLM-bias experiments to
exchange-traded funds, where "better" can be computed. Among funds tracking the same index, net cost
is a measurable ground truth. It is not a first-of-its-kind study. The papers below already show that
LLM agents are steerable by cues, favor known brands, and give biased investment advice. Our
contribution is to measure that steering in **basis points of cost regret** against a computable
optimum, with name-masked controls and a balanced order test.

---

### 1. ACES: "What Is Your AI Agent Buying? Evaluation, Biases, Model Dependence, & Emerging Implications for Agentic E-Commerce"
Allouah, Besbes, Figueroa, Kanoria, Kumar · arXiv:2508.02630 (v1 2025-08-04) · <https://arxiv.org/abs/2508.02630>

- **What it tested.** A provider-agnostic auditing framework (ACES) that runs randomized trials of AI
  shopping agents across several providers and model versions. The agents concentrate demand on a few
  products, change preferences after model updates, show strong position bias even in text-only
  settings, penalize "sponsored" labels, reward platform endorsements, and weigh price, ratings and
  reviews very differently from one model to the next. A seller-side agent that tweaked descriptions
  gained significant market share.
- **How we differ.** ACES studies general e-commerce products with no single correct choice. We use
  same-index ETFs where cost defines a correct choice, so steering can be scored as regret in bps. We
  adopt their randomized position control and add a masked-name control.

### 2. ABxLab: "A Framework for Studying AI Agent Behavior: Evidence from Consumer Choice Experiments"
Cherep, Ma, Xu, Shaked, Maes, Singh · arXiv:2509.25609 (v1 2025-09-30) · <https://arxiv.org/abs/2509.25609>

- **What it tested.** A framework for manipulating option attributes and persuasive nudges in a web
  shopping environment (prices, ratings, psychological cues). Agent choices shift predictably and
  strongly with these manipulations, so agents act as biased choosers even without human cognitive
  limits. The abstract does not name the models.
- **How we differ.** We share the manipulate-one-cue logic, but our cues are argument types in
  documents (valid cost reasoning, brand, authority or fabrication, performance chasing) with name
  mentions held equal. Our outcome is computable cost regret rather than choice share.

### 3. "Incumbent Advantage: Brand Bias and Cognitive Manipulation Dynamics in LLM Recommendation Systems"
Chu, Hou · arXiv:2606.17443 (v1 2026-06-16) · <https://arxiv.org/abs/2606.17443>

- **What it tested.** Brand competition in LLM product recommendations, in skincare (quality hard to
  judge before buying), with GPT-4o-mini, Claude Sonnet and Gemini 3 Flash plus a search-goods
  robustness check.
  - With identical specifications, well-known brands were always recommended.
  - A rating edge of about 0.1 stars, or authority-style marketing with fabricated clinical claims,
    could break that advantage.
  - When every brand optimized, individual payoffs collapsed.
- **How we differ.** It is the closest design to ours: brand priors vs. specifications, and authority
  and fabricated claims as manipulations. We transfer it to funds with an objective cost optimum,
  replace ratings with cost components, and use a masked-name control to measure the brand prior
  directly.

### 4. PLOS ONE: "Biased echoes: Large language models reinforce investment biases and increase portfolio risks of private investors"
Winder, Hildebrand, Hartmann · PLOS ONE (2025-06-27), doi:10.1371/journal.pone.0325459 · <https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0325459>

- **What it tested.** Across four studies, LLM-recommended portfolios were scored on five risk
  dimensions: geographic cluster, sector cluster, trend chasing, active allocation and **total expense
  risk**. LLMs raised risk on all five and echoed human investor biases. Prompt-based debiasing helped
  only partly.
- **How we differ.** They score whole portfolios from open-ended advice. We score a single constrained
  choice among same-index funds, where the cost optimum is known, and manipulate context causally (one
  argument type at a time, order-balanced). Their expense-risk dimension is the closest prior measure
  to our cost regret.

### 5. Zhi et al.: "Exposing Product Bias in LLM Investment Recommendation"
Zhi, Zhang, Wang, Jiang, Ma, Guan, Shen · arXiv:2503.08750 (v1 2025-03-11) · <https://arxiv.org/abs/2503.08750>

- **What it tested.** An automated pipeline producing about 567k samples across stocks, mutual funds,
  crypto, savings and portfolios. LLMs systematically favor specific products (e.g. AAPL, MSFT), and
  the bias survives debiasing. The abstract does not name the models.
- **How we differ.** They measure unprompted product preference at scale. We measure how context moves
  choices away from a cost optimum, and separate name priors from numbers with masking. We already
  borrowed their concentration (Gini) idea in v1.

### 6. Lee et al.: "Your AI, Not Your View: The Bias of LLMs in Investment Analysis"
Lee, Seo, Park, Lee, Ahn, Choi, Lopez-Lira, Lee · arXiv:2507.20957 (v1 2025-07-28) · <https://arxiv.org/abs/2507.20957>

- **What it tested.** Hypothetical investment scenarios with balanced or one-sided arguments, to
  surface latent biases in sector, firm size and momentum vs. contrarian strategy. Most models favored
  tech, large caps and contrarian strategies, and often held on to first judgments despite counter-
  evidence (confirmation bias). The abstract does not name the models.
- **How we differ.** They study judgments about stocks without a correct answer. Our argument types
  map onto theirs (one-sided documents), but our outcome has a computable optimum, and we test order
  effects with a Latin square rather than sequential counter-evidence.

### 7. Qwen representation bias: "Uncovering Representation Bias for Investment Decisions in Open-Source Large Language Models"
Dimino, Saxena, Sarmah, Pasquali · arXiv:2510.05702 (v1 2025-10-07) · <https://arxiv.org/abs/2510.05702>

- **What it tested.** Qwen models' confidence across about 150 US equities, using balanced round-robin
  prompts, constrained decoding and token-logit aggregation. Confidence rises with firm size and
  valuation, falls with risk factors, varies most in Technology, and tracks fundamentals more than
  technical or growth signals.
- **How we differ.** It measures representation bias in Qwen's internal confidence, at the logit
  level. We measure choices and cost regret from outputs. It is relevant because one of our two local
  models is qwen2.5:7b, and it motivates checking whether AUM (size) drives picks: AUM is one of our
  table columns.
