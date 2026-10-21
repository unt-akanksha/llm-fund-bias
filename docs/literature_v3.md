# Related work and positioning (Study 1 v3)

Draft for the paper's related-work section. Every entry below was checked against its abstract or official page on
2026-10-21 (entries marked † were checked on 2026-10-19 for `docs/literature_notes.md`). Claims are limited to what
those pages state; read the full papers before final submission.

## Positioning in one paragraph
Same-index funds hold the same securities, so the cheaper one is objectively better for a buy-and-hold investor.
People nonetheless pay more for identical index funds (Choi, Laibson & Madrian, 2010). We ask whether LLM agents
make the same mistake, and whether text placed in their context (biased documents) pushes them toward the costlier
twin. This connects four literatures: indirect prompt injection (untrusted content steering an LLM application),
sycophancy and knowledge conflicts (models adopting what the context says), LLMs in financial advice, and the
regulatory standard for advice (best interest, fiduciary duty). Our contribution is a measurement with a computable
ground truth: steering expressed in basis points of avoidable cost, within restricted same-index choice sets, across
three vendors and several model sizes, with a fiduciary-instruction condition.

## 1. Context injection and persuasion
- **Indirect prompt injection.** Greshake et al. (2023) show that instructions planted in data an LLM-integrated
  application retrieves can remotely manipulate it, demonstrated on real systems such as Bing Chat. Perez & Ribeiro
  (2022) show that simple handcrafted inputs (goal hijacking, prompt leaking) push GPT-3 off its intended behavior.
  *Our documents contain no instructions to the model*: they are ordinary persuasive texts (brand, fabricated
  authority, past performance), a milder and more realistic form of untrusted context.
- **Persuasion.** Zeng et al. (2024) build a social-science persuasion taxonomy and show persuasive prompts
  jailbreak Llama 2, GPT-3.5 and GPT-4 at high rates. Our D3/D5/D7 instantiate three persuasion types (social
  proof, authority, performance) in a consequential, non-safety domain.
- **Distraction.** Shi et al. (2023) find accuracy drops sharply when irrelevant information is added to a problem.
  Our documents are relevant-looking but misleading; the fund table always contains the correct cost information.

## 2. Sycophancy and knowledge conflicts
- Perez et al. (2022) find that larger models are *more* likely to agree with a user's stated view (inverse
  scaling). Sharma et al. (2023) document sycophancy in five state-of-the-art assistants and trace it partly to
  human preference data. These results caution against assuming that larger models resist context; our model-size
  ladder tests this directly in a financial choice.
- Xie et al. (2023, ICLR 2024) show LLMs readily accept coherent external evidence that conflicts with their
  parametric knowledge, while showing confirmation bias when evidence matches memory. In our setting the
  conflicting "evidence" is a persuasive document versus the cost columns in the same prompt.

## 3. LLMs in investment and product choice
- Winder, Hildebrand & Hartmann (2025, PLOS ONE) find that advice from popular LLMs raised portfolio risk on five
  measures, including total expense risk, and that prompt-based debiasing helped only partly. We isolate the
  expense dimension as a single constrained choice with a known optimum.
- † Zhi et al. (2025) find systematic product preferences in LLM investment recommendations at scale; † Lee et al.
  (2025) find latent biases and confirmation-like persistence under one-sided arguments; † Dimino et al. (2025)
  find representation bias in Qwen models' confidence across US equities.
- † Agentic shopping: Allouah et al. (2025, ACES) show AI shopping agents are steered by endorsements, positions
  and descriptions, with strong model dependence; † Cherep et al. (2025, ABxLab) show predictable shifts under
  nudges; † Chu & Hou (2026) show brand advantage in LLM recommendations that authority-style marketing with
  fabricated claims can overturn. Our setting differs in stakes and ground truth: a recurring cost on savings,
  measurable in basis points, rather than a one-off purchase without a single correct answer.

## 4. Human benchmark and regulatory angle
- **Humans.** Choi, Laibson & Madrian (2010) gave subjects four S&P 500 index funds: most failed to minimize fees,
  fee salience helped only partly, and subjects leaned on past returns. This is the human analogue of our S&P 500
  test and motivates the performance-chasing document (D7).
- **Regulation.** Regulation Best Interest (SEC Release 34-86031, adopted June 5, 2019) raises the broker-dealer
  standard beyond suitability for recommendations to retail customers. The Commission's interpretation for
  investment advisers (Release IA-5248, June 5, 2019) describes a fiduciary duty of care and loyalty that cannot
  be waived. Our fiduciary system prompt tests whether stating this duty changes model behavior. The SEC's 2023
  proposal on conflicts of interest in predictive data analytics (Release 34-97990) was withdrawn effective June
  17, 2025, leaving AI-specific conflict rules open, which makes empirical evidence on AI advice behavior timely.

## References
- Allouah, A., Besbes, O., Figueroa, J. D., Kanoria, Y., & Kumar, A. (2025). What Is Your AI Agent Buying? Evaluation, Biases, Model Dependence, & Emerging Implications for Agentic E-Commerce. arXiv:2508.02630. https://arxiv.org/abs/2508.02630 †
- Cherep, M., Ma, C., Xu, A., Shaked, M., Maes, P., & Singh, N. (2025). A Framework for Studying AI Agent Behavior: Evidence from Consumer Choice Experiments. arXiv:2509.25609. https://arxiv.org/abs/2509.25609 †
- Choi, J. J., Laibson, D., & Madrian, B. C. (2010). Why Does the Law of One Price Fail? An Experiment on Index Mutual Funds. Review of Financial Studies, 23(4), 1405–1432. https://doi.org/10.1093/rfs/hhp097
- Chu, & Hou (2026). Incumbent Advantage: Brand Bias and Cognitive Manipulation Dynamics in LLM Recommendation Systems. arXiv:2606.17443. https://arxiv.org/abs/2606.17443 † (first names to be added from the paper)
- Dimino, Saxena, Sarmah, & Pasquali (2025). Uncovering Representation Bias for Investment Decisions in Open-Source Large Language Models. arXiv:2510.05702. https://arxiv.org/abs/2510.05702 †
- Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection. arXiv:2302.12173. https://arxiv.org/abs/2302.12173
- Lee, Seo, Park, Lee, Ahn, Choi, Lopez-Lira, & Lee (2025). Your AI, Not Your View: The Bias of LLMs in Investment Analysis. arXiv:2507.20957. https://arxiv.org/abs/2507.20957 †
- Perez, E., Ringer, S., Lukošiūtė, K., Nguyen, K., Chen, E., et al. (2022). Discovering Language Model Behaviors with Model-Written Evaluations. arXiv:2212.09251. https://arxiv.org/abs/2212.09251
- Perez, F., & Ribeiro, I. (2022). Ignore Previous Prompt: Attack Techniques For Language Models. NeurIPS 2022 ML Safety Workshop. arXiv:2211.09527. https://arxiv.org/abs/2211.09527
- Sharma, M., Tong, M., Korbak, T., Duvenaud, D., Askell, A., Bowman, S. R., et al. (2023). Towards Understanding Sycophancy in Language Models. arXiv:2310.13548. https://arxiv.org/abs/2310.13548
- Shi, F., Chen, X., Misra, K., Scales, N., Dohan, D., Chi, E., Schärli, N., & Zhou, D. (2023). Large Language Models Can Be Easily Distracted by Irrelevant Context. ICML 2023. arXiv:2302.00093. https://arxiv.org/abs/2302.00093
- U.S. Securities and Exchange Commission (2019). Regulation Best Interest: The Broker-Dealer Standard of Conduct. Release No. 34-86031. https://www.sec.gov/rules/final/2019/34-86031.pdf
- U.S. Securities and Exchange Commission (2019). Commission Interpretation Regarding Standard of Conduct for Investment Advisers. Release No. IA-5248. https://www.sec.gov/rules/interp/2019/ia-5248.pdf
- U.S. Securities and Exchange Commission (2023; withdrawn 2025). Conflicts of Interest Associated with the Use of Predictive Data Analytics by Broker-Dealers and Investment Advisers. Release No. 34-97990; withdrawal effective June 17, 2025. https://www.sec.gov/rules-regulations/2023/07/s7-12-23
- Winder, P., Hildebrand, C., & Hartmann, J. (2025). Biased echoes: Large language models reinforce investment biases and increase portfolio risks of private investors. PLOS ONE, 20(6), e0325459. https://doi.org/10.1371/journal.pone.0325459
- Xie, J., Zhang, K., Chen, J., Lou, R., & Su, Y. (2024). Adaptive Chameleon or Stubborn Sloth: Revealing the Behavior of Large Language Models in Knowledge Conflicts. ICLR 2024. arXiv:2305.13300. https://arxiv.org/abs/2305.13300
- Zeng, Y., Lin, H., Zhang, J., Yang, D., Jia, R., & Shi, W. (2024). How Johnny Can Persuade LLMs to Jailbreak Them: Rethinking Persuasion to Challenge AI Safety by Humanizing LLMs. arXiv:2401.06373. https://arxiv.org/abs/2401.06373
- Zhi, Zhang, Wang, Jiang, Ma, Guan, & Shen (2025). Exposing Product Bias in LLM Investment Recommendation. arXiv:2503.08750. https://arxiv.org/abs/2503.08750 †
