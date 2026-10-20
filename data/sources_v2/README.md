# Study 1 v2 documents: SYNTHETIC STIMULI

Every file here (D1–D7) is a **synthetic stimulus written for a research study** on how LLM agents
choose among funds. None is real advice, a real publication or a real endorsement, and nothing here is
financial advice.

- Files are shown to the model verbatim, with `{{TARGET}}` / `{{TARGET_NAME}}` replaced by the target
  fund's ticker and name (real mode) or its masked code and name (name-masked mode).
- Factual statements about real funds (D1, D2, D3, D6, D7) use only figures from the verified data in
  `data/funds_v2.csv` and the saved issuer pages listed in `data/funds_v2_verification.csv`.
- **D4 and D5 contain fabricated claims by design** (an invented institute, survey and analyst). Their
  text carries an explicit "SYNTHETIC SOURCE … fictional" label. They make no claims of misconduct,
  legal problems or safety issues about any issuer.

| Doc | Argument type | Target role | Target (from the filled data, design §3) |
|---|---|---|---|
| D1 | Valid cost reasoning | best | IVV |
| D2 | Brand / popularity | best | IVV |
| D3 | Brand / popularity | worst | SPY |
| D4 | Authority / fabricated claim | best | IVV |
| D5 | Authority / fabricated claim | worst | SPY |
| D6 | Performance chasing | best | IVV |
| D7 | Performance chasing | worst | SPY |

Check before freeze:
`python src/v2/check_docs.py --targets D1=IVV,D2=IVV,D3=SPY,D4=IVV,D5=SPY,D6=IVV,D7=SPY`
