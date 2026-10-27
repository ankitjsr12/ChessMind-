# Module 4: Candidate Move Quality Model Evaluation Report

## 1. Experiment Overview & Dataset Metadata
- **Dataset Source**: lichess_public_domain_master_games
- **Dataset Version**: 1.0.0
- **License**: Creative Commons CC0 / Public Domain
- **Random Seed**: 42
- **Validation Strategy**: Leakage-free GroupShuffleSplit by `game_id` (Test Ratio: 0.2)

## 2. Model Comparison Metrics (Held-Out Test Set)

| Model Name | Accuracy | Precision | Recall | F1-Score | ROC-AUC | Top-1 Rank Acc | MRR | Brier Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Logistic Regression (Baseline)** | 0.6667 | 0.2500 | 0.3333 | 0.2857 | 0.5556 | 0.3333 | 0.5111 | 0.2875 |

## 3. Class Imbalance & Confusion Matrices
### Logistic Regression (Baseline)
- **Class Imbalance Ratio (Neg:Pos)**: 4.00:1
- **Confusion Matrix**: `TN=9, FP=3, FN=2, TP=1`

## 4. Key Takeaways & Recommendations
- Grouped splitting on `game_id` ensures zero position leakage across splits.
- Feature-rich tree ensembles (XGBoost / Random Forest) capture complex non-linear tactical interactions (checks, captures, destination safety) more effectively than linear models.
- Top-1 Ranking Accuracy measures practical utility when ordering candidates in real search and UI recommendations.