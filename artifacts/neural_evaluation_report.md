# Module 5: Neural Chess Position Evaluation Benchmark (CNN)

## 1. Overall Performance on Held-Out Test Positions
- **Sample Count**: 15 positions (Grouped by `game_id` without overlap)
- **Target Representation**: Continuous centipawn mapping via bounded $\tanh(\text{cp}/400.0)$

| Evaluation Method | MAE (Centipawns) | RMSE (Centipawns) | Sign Accuracy | Correlation ($r$) |
| :--- | :---: | :---: | :---: | :---: |
| **Neural Network (CNN)** | **153.1** | **204.4** | **35.71%** | **-0.2613** |
| **Material Baseline** | 64.3 | 79.5 | 64.29% | Baseline |

## 2. Game Phase Breakdown (Opening vs. Middlegame vs. Endgame)

| Game Phase | Positions | Neural MAE (cp) | Material MAE (cp) | Improvement |
| :--- | :---: | :---: | :---: | :---: |
| **Opening** | 9 | 64.1 | 61.4 | -2.6 cp |
| **Middlegame** | 6 | 286.8 | 68.5 | -218.3 cp |

## 3. Methodological Comparison (Module 4 ML vs. Module 5 Deep Learning)
- **Module 4 (Classical ML)**: Predicts *candidate move quality* given a position and candidate move. Learns tabular features (checks, captures, destination safety, piece-square tables) using XGBoost.
- **Module 5 (Deep Learning)**: Evaluates *whole board state strength* directly from raw 18-channel spatial bitboards. Learns non-linear spatial representations through convolutional residual blocks without human-engineered feature heuristics.

## 4. Limitations & Distribution Shift
- Neural evaluations trained on master games reflect positional conventions from competitive tournament play.
- In extreme tactical positions (e.g. forced checkmate in 5), deep alpha-beta search or Stockfish remains necessary to verify concrete tactical sequences.