"""Pytest configuration and environment safety."""

import os

# Prevent OpenMP runtime conflicts between PyTorch and XGBoost/scikit-learn on macOS
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
