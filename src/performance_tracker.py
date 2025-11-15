"""
Performance Tracking System

Tracks AI summary generation performance metrics to enable machine-specific
time estimates. Data is stored in a CSV file and used for regression-based
predictions after sufficient observations are collected.

Columns tracked:
- timestamp: ISO format timestamp of generation
- input_tokens: Approximate token count of input text
- input_documents: Number of documents processed
- requested_summary_length: Target summary length in words
- actual_summary_length: Actual generated summary length in words
- generation_time_seconds: Time taken to generate summary
- model_name: Model used (standard/pro)
"""

import os
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import numpy as np


class PerformanceTracker:
    """
    Tracks and predicts AI generation performance.

    Stores performance data in CSV format and provides time estimates
    based on historical data using simple linear regression.
    """

    # CSV file location
    PERFORMANCE_LOG = os.path.join(
        os.getenv('APPDATA', os.path.expanduser('~')),
        'LocalScribe',
        'performance_log.csv'
    )

    # Minimum observations needed for predictions
    MIN_OBSERVATIONS = 10

    # CSV columns
    COLUMNS = [
        'timestamp',
        'input_tokens',
        'input_documents',
        'requested_summary_length',
        'actual_summary_length',
        'generation_time_seconds',
        'model_name'
    ]

    def __init__(self):
        """Initialize performance tracker and ensure CSV exists."""
        self._ensure_csv_exists()

    def _ensure_csv_exists(self):
        """Create CSV file with headers if it doesn't exist."""
        os.makedirs(os.path.dirname(self.PERFORMANCE_LOG), exist_ok=True)

        if not os.path.exists(self.PERFORMANCE_LOG):
            with open(self.PERFORMANCE_LOG, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(self.COLUMNS)

    def log_generation(
        self,
        input_text: str,
        input_documents: int,
        requested_summary_length: int,
        actual_summary_length: int,
        generation_time_seconds: float,
        model_name: str
    ):
        """
        Log a completed summary generation to CSV.

        Args:
            input_text: Combined input text (used to estimate tokens)
            input_documents: Number of documents processed
            requested_summary_length: Target summary length in words
            actual_summary_length: Actual generated summary length in words
            generation_time_seconds: Time taken to generate
            model_name: Model used ('standard' or 'pro')
        """
        # Estimate input tokens (rough: 1.5 tokens per word)
        input_tokens = int(len(input_text.split()) * 1.5)

        # Create row
        row = [
            datetime.now().isoformat(),
            input_tokens,
            input_documents,
            requested_summary_length,
            actual_summary_length,
            round(generation_time_seconds, 2),
            model_name
        ]

        # Append to CSV
        with open(self.PERFORMANCE_LOG, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def get_observation_count(self, model_name: Optional[str] = None) -> int:
        """
        Get the number of logged observations.

        Args:
            model_name: Optional filter by model ('standard' or 'pro')

        Returns:
            Number of observations in log
        """
        try:
            with open(self.PERFORMANCE_LOG, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                if model_name:
                    count = sum(1 for row in reader if row['model_name'] == model_name)
                else:
                    count = sum(1 for row in reader)

                return count
        except Exception:
            return 0

    def can_predict(self, model_name: Optional[str] = None) -> bool:
        """
        Check if enough observations exist to make predictions.

        Args:
            model_name: Optional filter by model

        Returns:
            True if MIN_OBSERVATIONS or more exist
        """
        return self.get_observation_count(model_name) >= self.MIN_OBSERVATIONS

    def predict_generation_time(
        self,
        input_tokens: int,
        input_documents: int,
        requested_summary_length: int,
        model_name: str
    ) -> Optional[float]:
        """
        Predict generation time based on historical data.

        Uses multiple linear regression with features:
        - input_tokens
        - input_documents
        - requested_summary_length

        Args:
            input_tokens: Estimated input token count
            input_documents: Number of documents to process
            requested_summary_length: Target summary length
            model_name: Model to use ('standard' or 'pro')

        Returns:
            Predicted time in seconds, or None if insufficient data
        """
        if not self.can_predict(model_name):
            return None

        try:
            # Load historical data for this model
            data = self._load_historical_data(model_name)

            if len(data) < self.MIN_OBSERVATIONS:
                return None

            # Prepare features (X) and target (y)
            X = []
            y = []

            for row in data:
                X.append([
                    float(row['input_tokens']),
                    float(row['input_documents']),
                    float(row['requested_summary_length'])
                ])
                y.append(float(row['generation_time_seconds']))

            X = np.array(X)
            y = np.array(y)

            # Simple linear regression: y = X * beta
            # Solve using normal equation: beta = (X^T * X)^-1 * X^T * y

            # Add intercept term (column of ones)
            X_with_intercept = np.column_stack([np.ones(len(X)), X])

            # Calculate coefficients
            beta = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]

            # Predict for new input
            new_X = np.array([1, input_tokens, input_documents, requested_summary_length])
            predicted_time = np.dot(new_X, beta)

            # Ensure non-negative prediction
            predicted_time = max(0, predicted_time)

            return predicted_time

        except Exception as e:
            # If prediction fails, return None
            print(f"Prediction error: {e}")
            return None

    def _load_historical_data(self, model_name: str) -> List[Dict]:
        """
        Load historical data from CSV for specific model.

        Args:
            model_name: Model to filter by

        Returns:
            List of row dictionaries
        """
        data = []

        try:
            with open(self.PERFORMANCE_LOG, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    if row['model_name'] == model_name:
                        data.append(row)

        except Exception:
            pass

        return data

    def get_average_time(self, model_name: Optional[str] = None) -> Optional[float]:
        """
        Get average generation time from historical data.

        Useful as a fallback estimate before predictions are available.

        Args:
            model_name: Optional filter by model

        Returns:
            Average time in seconds, or None if no data
        """
        try:
            with open(self.PERFORMANCE_LOG, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                times = []
                for row in reader:
                    if model_name is None or row['model_name'] == model_name:
                        times.append(float(row['generation_time_seconds']))

                if times:
                    return sum(times) / len(times)
                else:
                    return None

        except Exception:
            return None


# Singleton instance
_tracker_instance = None


def get_performance_tracker() -> PerformanceTracker:
    """Get or create the global PerformanceTracker instance."""
    global _tracker_instance

    if _tracker_instance is None:
        _tracker_instance = PerformanceTracker()

    return _tracker_instance
