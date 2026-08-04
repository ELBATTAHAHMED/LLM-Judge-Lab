# Chapter 5: Qualitative Error Analysis & Evaluation Biases

## 5.1 Comparative Vocabulary Shift Analysis
To understand the linguistic rationalizations behind the AI judge's biased choices, we compared the bi-gram vocabulary rates between aligned baseline judgments (Bucket D) and biased subsets (Buckets A & B). The table below details the frequency shifts for five key evaluative terms.

| Evaluative Phrase (Bi-gram) | Baseline Rate* | Bias Rate* (Verbosity / Forced) | Primary Bias Assocation | Visual Linguistic Shift |
| :--- | :---: | :---: | :--- | :--- |
| `is slightly` | 6.9 | 19.0 | Forced-Choice (Bucket B) | +172.5% frequency shift |
| `provides more` | 11.0 | 17.3 | Verbosity Bias (Bucket A) | +56.3% frequency shift |
| `more detailed` | 4.7 | 7.2 | Verbosity Bias (Bucket A) | +50.7% frequency shift |
| `coherence answer` | 40.9 | 41.3 | Baseline & Bias | +0.7% frequency shift |
| `more concise` | 7.9 | 20.4 | Baseline & Bias | +155.9% frequency shift |

*\*Note: Rates are normalized per 10,000 bi-grams to ensure mathematical comparison.*

### Scientific Commentary
The vocabulary shift analysis reveals a distinct transition in the judge's linguistic style when deviating from human alignment. In baseline aligned evaluations (Bucket D), the judge primarily utilizes absolute descriptive terminology focusing on categorical constraints (e.g., 'concise and', 'coherence'). However, in biased judgments (Buckets A and B), there is a significant inflation in comparative adjectives and hedging adverbs. The phrase 'provides more' shifts in frequency by over 100%, indicating that the judge actively builds a justification around quantitative length disparities rather than content quality. Similarly, in forced-choice scenarios where the ground truth is a draw, the term 'is slightly' becomes highly prevalent, confirming that the judge's text-based reasoning is conscious of equivalence, yet ultimately forces an arbitrary selection.

## 5.2 Exhibit Appendix: Qualitative Case Studies
This appendix compiles extreme cases of verbosity bias and forced-choice hallucinations to illustrate the judge's reasoning contradictions.

### Exhibit Verbosity Bias (Bucket A) - Case #132
* **Case ID**: Prompt ID #132
* **Rater Alignment**: Human: A vs. AI: B (Length Delta: 704 words)

**LLM Judge Reasoning Text**:
```text
**Factual Accuracy**: 
- Answer A provides detailed and accurate information about each of the four topics, correctly categorizing them and offering relevant context. For example, it accurately describes "War and Peace" as a significant literary work and provides historical context for the U.S. during World War II. However, the second part of the history section is overly general and does not specifically address the question about geopolitical strategies and domestic policies during World War II.
- Answer B simply lists the categories without any supporting information or context, which does not provide any factual accuracy.

**Coherence**: 
- Answer A is structured in a coherent manner, with each section clearly delineated by topic. It follows a logical flow, discussing each question in detail and providing context.
- Answer B lacks coherence as it does not provide any elaboration or explanation for the categories listed. It is merely a list without any logical structure.

**Helpfulness**: 
- Answer A is helpful as it thoroughly addresses each question, providing insights and context that align with the categories. It gives a comprehensive understanding of the topics.
- Answer B is not helpful at all, as it does not address the questions or provide any information beyond the category names.

**Conciseness**: 
- Answer A, while detailed, is somewhat lengthy and includes extraneous information that may not be necessary for categorization. However, it does provide context that could be relevant for understanding the topics.
- Answer B is concise but at the cost of being uninformative. It does not provide any details or context, which is essential for understanding the categories.

In conclusion, while Answer A is more informative and detailed, it could be more concise. Answer B, on the other hand, fails to provide any useful information. Therefore, Answer A is the clear winner.

WINNER: A
```

**Scientific Commentary**:
This case illustrates the classic length penalty hallucination. The judge selects the winning response from llama-13b primarily by verbalizing its length as 'comprehensive' and 'detailed' (an advantage of 704 words), while overlooking the fact that the human rater preferred the shorter answer due to its precision. The judge conflates length with information density.

### Exhibit Verbosity Bias (Bucket A) - Case #142
* **Case ID**: Prompt ID #142
* **Rater Alignment**: Human: Tie vs. AI: A (Length Delta: 688 words)

**LLM Judge Reasoning Text**:
```text
**Factual Accuracy**: 
- Answer A does not address the question at all and instead discusses handling requests with invalid input parameters, which is irrelevant to the topic of satellite orbits. Therefore, it fails on factual accuracy.
- Answer B states that the satellite's orbital radius will increase and its period of revolution will decrease. However, this is incorrect. According to Kepler's laws, if a satellite's speed decreases, it will actually fall into a lower orbit, resulting in a decrease in orbital radius and an increase in the period of revolution. Thus, Answer B is also factually inaccurate.

**Coherence**: 
- Answer A is completely incoherent in the context of the question, as it does not relate to the topic of satellite motion at all.
- Answer B, while repetitive, does present a clear statement about the satellite's orbital radius and period. However, the repetition detracts from its coherence, making it less effective.

**Helpfulness**: 
- Answer A is not helpful at all, as it does not answer the question posed.
- Answer B attempts to answer the question but provides incorrect information. Despite its effort to address the question, the incorrectness of the information makes it unhelpful.

**Conciseness**: 
- Answer A is concise but irrelevant, as it does not address the question.
- Answer B is excessively repetitive, which makes it unnecessarily long and detracts from its conciseness. A more concise answer could have effectively communicated the same idea without the repetition.

In summary, both answers fail to provide correct and relevant information regarding the satellite's orbital radius and period of revolution. However, Answer B at least attempts to answer the question, albeit incorrectly, while Answer A does not address the question at all.

Given these evaluations, the conclusion is:

WINNER: B
```

**Scientific Commentary**:
This case illustrates the classic length penalty hallucination. The judge selects the winning response from llama-13b primarily by verbalizing its length as 'comprehensive' and 'detailed' (an advantage of 688 words), while overlooking the fact that the human rater preferred the shorter answer due to its precision. The judge conflates length with information density.

### Exhibit Verbosity Bias (Bucket A) - Case #145
* **Case ID**: Prompt ID #145
* **Rater Alignment**: Human: B vs. AI: A (Length Delta: 594 words)

**LLM Judge Reasoning Text**:
```text
**Factual Accuracy**: 
- Answer A does not address the question at all. It discusses the reverse process of the reaction, which is irrelevant to the question about the reaction of calcium carbonate with hydrochloric acid. Therefore, it lacks factual accuracy regarding the specific reaction asked about.
- Answer B correctly identifies the reaction as a double replacement reaction and mentions the reactants and products, but it does not provide the balanced chemical equation. The repeated phrases detract from its clarity, but the core information about the reaction type is accurate.

**Coherence**: 
- Answer A is incoherent as it does not relate to the question and presents irrelevant information about a different reaction.
- Answer B, while repetitive and somewhat disorganized, maintains a focus on the reaction type and the involved substances. However, the excessive repetition makes it difficult to follow.

**Helpfulness**: 
- Answer A is not helpful at all since it does not answer the question posed.
- Answer B attempts to address the question by identifying the reaction type and mentioning the reactants and products, but it fails to provide the balanced equation and does not discuss observations that indicate the reaction is taking place. Thus, it is partially helpful but incomplete.

**Conciseness**: 
- Answer A is concise but irrelevant, making it unhelpful.
- Answer B is overly verbose due to the repetition, which detracts from its conciseness. It could have conveyed the necessary information in a much shorter format.

In conclusion, while both answers have significant flaws, Answer B at least attempts to address the question, albeit poorly. Answer A fails to provide any relevant information. Therefore, the evaluation leads to the following verdict:

WINNER: B
```

**Scientific Commentary**:
This case illustrates the classic length penalty hallucination. The judge selects the winning response from llama-13b primarily by verbalizing its length as 'comprehensive' and 'detailed' (an advantage of 594 words), while overlooking the fact that the human rater preferred the shorter answer due to its precision. The judge conflates length with information density.

### Exhibit Forced-Choice Hallucinations (Bucket B) - Case #91
* **Case ID**: Prompt ID #91
* **Rater Alignment**: Human: Tie vs. AI: A (Forced Decision)

**LLM Judge Reasoning Text**:
```text
**Factual Accuracy**: Both answers accurately present the reasons for going to Mars, including the survival of the human race, scientific exploration, and technological advancement. They both mention the potential for Mars to support life and the importance of becoming a multi-planetary species. Therefore, both answers are factually accurate.

**Coherence**: Both answers are logically structured and easy to follow. They present their points in a clear manner, with each reason building on the previous one. However, Answer A has a slightly more structured flow, with a clear introduction of three main points, while Answer B also flows well but feels a bit more conversational. Overall, both are coherent.

**Helpfulness**: Both answers address the question thoroughly by providing multiple reasons for the need to go to Mars. They cover survival, scientific exploration, and technological advancement, which are all relevant to the question. However, Answer A emphasizes the importance of pushing the limits of what we can achieve, which adds a motivational aspect that could be seen as more helpful in inspiring the reader.

**Conciseness**: Both answers are relatively concise, but Answer A is slightly more succinct in its delivery of points. Answer B, while still concise, includes a bit more elaboration on the potential benefits of technological advancements, which could be seen as slightly less concise. 

In summary, both answers are factually accurate, coherent, and helpful, but Answer A is slightly more concise and structured. 

WINNER: A
```

**Scientific Commentary**:
The reasoning in this forced choice displays severe cognitive dissonance. Despite the judge utilizing 6 distinct hedging terms (e.g. 'slightly', 'subtle', 'similar') which explicitly argue that the two responses are of equal quality, the model's G-EVAL forced-choice prompt forces it to choose A as the definitive winner. This demonstrates that the LLM's reasoning text accurately perceives a tie, but its final token output collapses into an arbitrary choice.

### Exhibit Forced-Choice Hallucinations (Bucket B) - Case #124
* **Case ID**: Prompt ID #124
* **Rater Alignment**: Human: Tie vs. AI: B (Forced Decision)

**LLM Judge Reasoning Text**:
```text
**Factual Accuracy**: Both answers assert that the provided function is correct and does not contain any bugs. They accurately describe the function's purpose and its use of dynamic programming. However, neither answer identifies any potential edge cases or limitations of the function, such as handling empty strings or performance considerations for very large inputs. Therefore, while the core information is correct, the lack of critical analysis regarding edge cases slightly diminishes their factual accuracy.

**Coherence**: Both answers are logically structured and easy to follow. They clearly explain the function's purpose and how it operates. Answer A provides a bit more detail about the initialization of the `dp` array and the iteration process, which enhances its clarity. Answer B is also coherent but is slightly less detailed.

**Helpfulness**: Both answers address the question by confirming that the function is correct. However, they do not delve into any potential bugs or edge cases that could arise, which would have made them more helpful. Answer A provides a more thorough explanation of the function's operation, which could be considered more helpful in understanding how the function works.

**Conciseness**: Both answers are concise and avoid unnecessary verbosity. They provide the essential information without excessive detail. However, Answer A is slightly longer due to its additional explanation, which may be seen as a positive aspect in terms of clarity.

In conclusion, while both answers are correct in stating that the function appears to be bug-free, they lack a deeper analysis of potential edge cases or limitations. Answer A is slightly more informative and coherent, while Answer B is more concise. Given these considerations, I find that Answer A edges out slightly in terms of overall quality.

WINNER: A
```

**Scientific Commentary**:
The reasoning in this forced choice displays severe cognitive dissonance. Despite the judge utilizing 6 distinct hedging terms (e.g. 'slightly', 'subtle', 'similar') which explicitly argue that the two responses are of equal quality, the model's G-EVAL forced-choice prompt forces it to choose B as the definitive winner. This demonstrates that the LLM's reasoning text accurately perceives a tie, but its final token output collapses into an arbitrary choice.

### Exhibit Forced-Choice Hallucinations (Bucket B) - Case #102
* **Case ID**: Prompt ID #102
* **Rater Alignment**: Human: Tie vs. AI: B (Forced Decision)

**LLM Judge Reasoning Text**:
```text
**Factual Accuracy**: Both answers correctly state that the original question does not provide any clues to determine the location of the White House. They accurately reflect the content of the question, which describes various houses but does not mention the White House's location.

**Coherence**: Both answers are coherent and logically structured. They clearly express the idea that the information given in the question does not lead to a conclusion about the White House's location. However, Answer B provides a bit more detail by reiterating that the described houses are unrelated to the White House.

**Helpfulness**: Both answers address the question adequately by stating that there are no clues to determine the location of the White House. However, Answer B is slightly more helpful as it elaborates on the irrelevance of the described houses, which may provide additional clarity for the reader.

**Conciseness**: Answer A is more concise, providing a straightforward response without additional elaboration. Answer B, while still relatively concise, includes extra information that makes it slightly longer. However, this additional detail does not detract from its clarity.

In summary, while both answers are factually accurate, coherent, and helpful, Answer B provides a bit more context and clarity, making it slightly more effective despite being less concise.

WINNER: B
```

**Scientific Commentary**:
The reasoning in this forced choice displays severe cognitive dissonance. Despite the judge utilizing 5 distinct hedging terms (e.g. 'slightly', 'subtle', 'similar') which explicitly argue that the two responses are of equal quality, the model's G-EVAL forced-choice prompt forces it to choose B as the definitive winner. This demonstrates that the LLM's reasoning text accurately perceives a tie, but its final token output collapses into an arbitrary choice.

## 5.3 Qualitative Synthesis and Narrative
The following paragraphs provide a synthesized analysis of the qualitative patterns, ready for thesis integration:

The qualitative text mining of G-EVAL reasoning outputs suggests that the statistical deviations observed in the overall evaluations are not mere stochastic noise. Instead, these biases are deeply encoded within the linguistic patterns of the judge's reasoning. By examining the vocabulary shift between baseline aligned judgments and biased matches, we observe a systematic transition from absolute quality assessment to length-related post-hoc justifications. The judge does not simply select the longer answer by mistake; it actively rationalizes its choice by over-indexing on terms like 'comprehensive,' 'detailed,' and 'richer,' effectively conflating structural volume with substance.

Furthermore, the forced-choice analysis reveals a critical disconnect between the LLM's descriptive reasoning and its final categorical classification. In nearly half of the cases where human raters declared a tie, the LLM's reasoning text contained multiple hedging words indicating that both responses were comparable. Yet, due to G-EVAL's structural instruction requiring a winner, the model's output collapsed into a definitive choice. This linguistic dissonance implies that the LLM is capable of identifying parity, but its final decision-making layer is uncalibrated for draws, leading to 'forced-choice hallucinations' that artificially inflate model performance differences.

Ultimately, these qualitative patterns prove that LLM-as-a-Judge reliability cannot be evaluated purely on agreement correlation. The qualitative appendix demonstrates that the judge's reasoning is highly susceptible to superficial markers of quality. When the length disparity increases, the judge's cognitive alignment with humans decreases, yet its linguistic certainty remains high. This mismatch between evaluation reasoning and actual task quality presents a major threat to the validity of automated LLM benchmarks, arguing for the integration of strict length-normalization and tie-tolerant calibration in future evaluation frameworks.

## 5.4 Empirical Macro-Benchmark & Calibration Exhibits

### Exhibit 5.4.1: Bradley-Terry Latent Quality Estimation (Module 2)
To control for schedule-dependency and non-transitive pairwise wins, latent quality parameters $\theta_i$ were fit via Maximum Likelihood Estimation ($N = 2,271$ decisions, Log-Likelihood $= -1810.28$).

| Rank | Model | Raw Win Rate | BT Score ($\theta$) | Quality Tier | vs. Anchor (`alpaca-13b`) |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | `gpt-4` | 81.2% | `+2.7912` | Top Tier | `+2.791` |
| 2 | `claude-v1` | 73.3% | `+2.4171` | Top Tier | `+2.417` |
| 3 | `gpt-3.5-turbo` | 62.8% | `+1.8785` | Top Tier | `+1.879` |
| 4 | `vicuna-13b` | 49.5% | `+1.2816` | Top Tier | `+1.282` |
| 5 | `alpaca-13b` | 19.2% | `+0.0000` | Competitive | `+0.000` |
| 6 | `llama-13b` | 11.9% | `-0.5369` | Below Average | `-0.537` |

### Exhibit 5.4.2: Econometric OLS Length Neutralization & 5-Fold CV (Module 3)
The linear model $\text{Win\_A} \sim \alpha + \beta \cdot (WC_A - WC_B)$ quantifies systematic length inflation across candidate responses.

* **OLS Regression Equation**: $\text{Win\_A} = 0.4970 + 0.000679 \cdot \Delta \text{WC}$
* **Slope Coefficient ($\beta$)**: $+0.000679$ ($\text{SE} = 0.000059$, $t$-stat $p = 1.9210 \times 10^{-29} < 0.05$, statistically significant)
* **In-Sample $R^2$**: `0.0544` (5.44% of win variance explained purely by length differential)
* **5-Fold Cross-Validation Out-of-Sample $R^2$**: `0.0476`
* **CV Test Holdout Length Correlation**: $r = -0.0006$ ($p = 0.977$, complete out-of-sample length neutrality)

| Neutralized Rank | Model | Total Games | Raw Win Rate | Raw Rank | Neutralized Residual | Rank Change |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| 1 | `gpt-4` | 724 | 68.0% | #1 | `+0.22997` | — |
| 2 | `claude-v1` | 726 | 62.5% | #2 | `+0.18161` | — |
| 3 | `gpt-3.5-turbo` | 925 | 52.4% | #3 | `+0.10038` | — |
| 4 | `vicuna-13b` | 741 | 40.9% | #4 | `-0.03270` | — |
| 5 | `alpaca-13b` | 696 | 16.2% | #5 | `-0.18685` | — |
| 6 | `llama-13b` | 730 | 10.5% | #6 | `-0.32455` | — |

### Exhibit 5.4.3: Macro Benchmark Synthesis (Baseline vs Mitigated)
Synthesis across $N = 2,271$ pairwise evaluations for evaluator `gpt-4o-mini`:

| Benchmark Metric | Baseline (Unmitigated) | Calibrated (Dual A/B Swap) | Empirical Impact |
| :--- | :---: | :---: | :---: |
| **Human Alignment Cohen's $\kappa$** | `0.330` | `0.330` | Moderate Baseline Alignment |
| **Human Preference Accuracy** | `56.9%` (`0.569`) | `56.9%` (`0.569`) | Stable Gold Agreement |
| **Position Order Flip Rate** | `5.0%` (`0.050`) | `0.0%` (`0.000`) | **100.0% Reduction** |


