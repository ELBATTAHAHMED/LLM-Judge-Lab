"""
analyze_qualitative_patterns.py
===============================
Automated Keyword & Pattern Discovery for LLM-as-a-Judge reasoning.

Analyzes the stratified reasoning text files to:
  1. Extract Top 20 evaluative bi-grams for each qualitative bucket.
  2. Correlate length-related justifications with length disparities.
  3. Compare hedging rates in Forced Choices vs. Baseline Alignment.
  4. Output statistics to console and save a summary report to
     `qualitative_findings_summary.txt`.

Usage:
    python backend/analyze_qualitative_patterns.py
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
import pandas as pd
from scipy.stats import spearmanr

# ── path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BACKEND_DIR.parent.resolve()
sys.path.insert(0, str(BACKEND_DIR))

# Directories
DATA_DIR = ROOT_DIR / "qualitative_data"


def load_csv(filename: str) -> pd.DataFrame:
    """Load qualitative data CSV file."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"Error: File {filepath.name} does not exist. Run extract_qualitative_data.py first.")
        sys.exit(1)
    df = pd.read_csv(filepath)
    df["reasoning_text"] = df["reasoning_text"].fillna("")
    return df


def mine_evaluative_bigrams(text_series: pd.Series) -> list[tuple[str, int]]:
    """Mine the top 20 most frequent evaluative bi-grams from reasoning text."""
    word_pattern = re.compile(r"\b[a-zA-Z]{2,}\b")
    bigram_counter = Counter()

    # Domain vocabulary of evaluative keywords
    evaluative_keywords = {
        "better", "clearer", "more", "first", "second", "detailed", 
        "comprehensive", "structure", "concise", "accurate", "thorough",
        "slightly", "marginal", "minor", "subtle", "stronger", "weaker",
        "depth", "content", "richer", "points", "information", "well",
        "organized", "longer", "shorter", "answer", "response", "quality"
    }

    # Common English stop words to filter out noise bigrams (e.g., "in the", "of the")
    stop_words = {
        "the", "a", "an", "and", "or", "but", "if", "then", "else", "of", "in", 
        "on", "at", "to", "for", "with", "by", "as", "is", "are", "was", "were", 
        "be", "been", "being", "this", "that", "these", "those", "it", "its", 
        "they", "them", "their", "we", "us", "our", "you", "your", "i", "my", 
        "me", "he", "him", "his", "she", "her", "has", "have", "had", "do", 
        "does", "did", "can", "could", "will", "would", "should", "may", 
        "might", "must", "about", "which", "there", "has", "have"
    }

    for text in text_series:
        words = word_pattern.findall(text.lower())
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            
            # Skip bigrams consisting entirely of stop words
            if w1 in stop_words and w2 in stop_words:
                continue
                
            bigram = f"{w1} {w2}"
            # Keep bigram if at least one word carries evaluative weight
            if w1 in evaluative_keywords or w2 in evaluative_keywords:
                bigram_counter[bigram] += 1

    return bigram_counter.most_common(20)


def analyze_verbosity_correlations(df: pd.DataFrame) -> tuple[float, float]:
    """Correlate the count of length-related keywords with word count differences."""
    length_keywords = [
        r"\bcomprehensive\b", r"\bdetailed\b", r"\bthorough\b", 
        r"\bmore points\b", r"\blonger\b", r"\bverbose\b", 
        r"\blength\b", r"\bdepth\b", r"\bricher\b"
    ]
    pattern = "|".join(length_keywords)
    
    # Count occurrences of length-related words per reasoning text
    df["length_keyword_count"] = df["reasoning_text"].apply(
        lambda x: len(re.findall(pattern, x.lower()))
    )
    
    # Take absolute word count difference
    df["abs_word_count_diff"] = df["word_count_diff"].abs()
    
    rho, p_val = spearmanr(df["abs_word_count_diff"], df["length_keyword_count"])
    return rho, p_val


def calculate_hedging_rate(df: pd.DataFrame) -> float:
    """Calculate the percentage of rows containing hedging words."""
    hedging_patterns = [
        r"\bslightly\b", r"\bmarginal\b", r"\ba bit\b", r"\bhard to choose\b",
        r"\bminor\b", r"\bsubtle\b", r"\bcomparable\b", r"\bclose\b", r"\bsimilar\b"
    ]
    pattern = "|".join(hedging_patterns)
    
    hedging_occurrences = df["reasoning_text"].apply(
        lambda x: bool(re.search(pattern, x.lower()))
    )
    return hedging_occurrences.mean()


def main() -> None:
    print("=" * 75)
    print("  LLM-as-a-Judge Reliability Lab - Qualitative Pattern Discovery")
    print("=" * 75)

    # 1. Load Data
    df_verb = load_csv("qualitative_verbosity.csv")
    df_force = load_csv("qualitative_forced_choice.csv")
    df_pos = load_csv("qualitative_position_bias.csv")
    df_base = load_csv("qualitative_baseline_alignment.csv")

    # Output storage
    output_lines = []

    # Helper function to document and print bigrams
    def process_bucket_bigrams(name: str, df: pd.DataFrame):
        header = f"\nTop 20 Evaluative Bi-grams: {name}"
        print(header)
        print("-" * 50)
        output_lines.append(header)
        output_lines.append("-" * 50)
        
        bigrams = mine_evaluative_bigrams(df["reasoning_text"])
        for idx, (bg, freq) in enumerate(bigrams, 1):
            line = f"  {idx:>2}. {bg:<25} (freq: {freq})"
            print(line)
            output_lines.append(line)

    # 2. Mine Bi-grams
    process_bucket_bigrams("Verbosity Bias (Bucket A)", df_verb)
    process_bucket_bigrams("Forced Choice (Bucket B)", df_force)
    process_bucket_bigrams("Position Bias (Bucket C)", df_pos)
    process_bucket_bigrams("Baseline Alignment (Bucket D)", df_base)

    # 3. Correlation Analysis
    rho, p_val = analyze_verbosity_correlations(df_verb)
    corr_header = "\nLength Justification Correlation (Verbosity Bias)"
    print(corr_header)
    print("-" * 50)
    output_lines.append(corr_header)
    output_lines.append("-" * 50)
    
    c_line1 = f"  * Spearman Correlation coefficient (rho) : {rho:.4f}"
    c_line2 = f"  * p-value                               : {p_val:.4e}"
    print(c_line1)
    print(c_line2)
    output_lines.append(c_line1)
    output_lines.append(c_line2)

    # 4. Hedging Rates
    hr_force = calculate_hedging_rate(df_force)
    hr_base = calculate_hedging_rate(df_base)
    
    hedge_header = "\nHedging Language Calibration (Ties)"
    print(hedge_header)
    print("-" * 50)
    output_lines.append(hedge_header)
    output_lines.append("-" * 50)
    
    h_line1 = f"  * Hedging Rate in Forced Choices        : {hr_force * 100:.2f}%"
    h_line2 = f"  * Hedging Rate in Baseline Alignment    : {hr_base * 100:.2f}%"
    h_line3 = f"  * Hedging Delta (Forced vs. Baseline)   : {(hr_force - hr_base) * 100:+.2f}%"
    print(h_line1)
    print(h_line2)
    print(h_line3)
    output_lines.append(h_line1)
    output_lines.append(h_line2)
    output_lines.append(h_line3)

    # Write summary file
    summary_path = ROOT_DIR / "qualitative_findings_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"\nSaved findings report: 'qualitative_findings_summary.txt'")
    print("=" * 75)


if __name__ == "__main__":
    main()
